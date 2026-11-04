"""
auth.py - Authentication, Authorization and Password Hashing
Handles student registration, user login validation, session guards, and role checks.
"""

from functools import wraps
import re
from flask import session, redirect, url_for, flash, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import models

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

def hash_password(password: str) -> str:
    """Hashes a plain-text password using Werkzeug's secure hashing."""
    return generate_password_hash(password, method='pbkdf2:sha256')

def verify_password(stored_hash: str, password: str) -> bool:
    """Verifies a plain-text password against the stored password hash."""
    return check_password_hash(stored_hash, password)

def register_student(name: str, email: str, password: str, confirm_password: str):
    """
    Validates input fields, verifies email uniqueness, hashes password,
    and registers a new student record.
    Returns (success: bool, message: str, student_id: int | None)
    """
    name = (name or "").strip()
    email = (email or "").strip().lower()
    password = password or ""
    confirm_password = confirm_password or ""

    if not name or len(name) < 2:
        return False, "Please provide a valid full name (minimum 2 characters).", None

    if not email or not EMAIL_REGEX.match(email):
        return False, "Please provide a valid email address.", None

    if len(password) < 6:
        return False, "Password must be at least 6 characters long.", None

    if password != confirm_password:
        return False, "Passwords do not match.", None

    existing = models.get_student_by_email(email)
    if existing:
        return False, "A student account with this email already exists.", None

    pwd_hash = hash_password(password)
    student_id = models.create_student(name, email, pwd_hash)
    return True, "Registration successful! You may now log in.", student_id

def authenticate_student(email: str, password: str):
    """
    Verifies student credentials.
    Returns (success: bool, message: str, student: dict | None)
    """
    email = (email or "").strip().lower()
    password = password or ""

    if not email or not password:
        return False, "Email and password are required.", None

    student = models.get_student_by_email(email)
    if not student:
        return False, "Invalid email or password.", None

    if not verify_password(student['password_hash'], password):
        return False, "Invalid email or password.", None

    # Exclude password hash from returned object for security
    student_dict = {
        "student_id": student["student_id"],
        "name": student["name"],
        "email": student["email"],
        "created_at": student["created_at"],
        "role": "student"
    }
    return True, "Login successful.", student_dict

def authenticate_admin(username: str, password: str):
    """
    Verifies administrator credentials.
    Returns (success: bool, message: str, admin: dict | None)
    """
    username = (username or "").strip()
    password = password or ""

    if not username or not password:
        return False, "Username and password are required.", None

    admin = models.get_admin_by_username(username)
    if not admin:
        return False, "Invalid username or password.", None

    if not verify_password(admin['password_hash'], password):
        return False, "Invalid username or password.", None

    admin_dict = {
        "admin_id": admin["admin_id"],
        "username": admin["username"],
        "role": "admin"
    }
    return True, "Admin login successful.", admin_dict

# ==================== ROUTE GUARDS / DECORATORS ====================

def student_login_required(f):
    """Decorator ensuring that an authenticated student is logged into session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session or session.get('role') != 'student':
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "Authentication required. Please log in as a student."}), 401
            flash("Please log in as a student to access this page.", "warning")
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator ensuring that an authenticated admin is logged into session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session or session.get('role') != 'admin':
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "Admin privileges required."}), 403
            flash("Administrator login required to access the admin portal.", "danger")
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function
