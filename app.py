"""
app.py - Main Flask Web Application for OSCN Project 04
Library Book Issue & Reservation System Using Python Mutex Synchronization

Coordinates web routes, JSON APIs, session state, template rendering,
and integrates with authentication, business logic, and concurrency modules.
"""

import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import database
import models
import auth
import library
import concurrency

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "oscn_project_04_mutex_secret_key_2026")

# Ensure database tables and initial sample data exist upon startup
with app.app_context():
    database.init_db(seed=True)

# Context processor to inject user session info into all Jinja2 templates
@app.context_processor
def inject_user_context():
    user_info = None
    if 'student_id' in session:
        user_info = {
            "id": session['student_id'],
            "name": session.get('name'),
            "email": session.get('email'),
            "role": "student"
        }
    elif 'admin_id' in session:
        user_info = {
            "id": session['admin_id'],
            "name": session.get('username'),
            "username": session.get('username'),
            "role": "admin"
        }
    return {
        "current_user": user_info,
        "now_year": datetime.now().year
    }

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/')
def index():
    if 'student_id' in session:
        return redirect(url_for('dashboard'))
    elif 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        # Check if JSON or Form
        data = request.get_json(silent=True) or request.form
        role = data.get('role', 'student').lower()
        
        if role == 'admin':
            username = data.get('username') or data.get('email')
            password = data.get('password')
            ok, msg, admin_data = auth.authenticate_admin(username, password)
            if ok:
                session.clear()
                session['admin_id'] = admin_data['admin_id']
                session['username'] = admin_data['username']
                session['role'] = 'admin'
                if request.is_json:
                    return jsonify({"success": True, "message": msg, "redirect": url_for('admin_dashboard')})
                flash(f"Welcome back, Administrator {admin_data['username']}!", "success")
                return redirect(url_for('admin_dashboard'))
            else:
                if request.is_json:
                    return jsonify({"success": False, "error": msg}), 401
                flash(msg, "danger")
                return render_template('login.html', error=msg, role=role)

        else: # Student
            email = data.get('email')
            password = data.get('password')
            ok, msg, student_data = auth.authenticate_student(email, password)
            if ok:
                session.clear()
                session['student_id'] = student_data['student_id']
                session['name'] = student_data['name']
                session['email'] = student_data['email']
                session['role'] = 'student'
                if request.is_json:
                    return jsonify({"success": True, "message": msg, "redirect": url_for('dashboard')})
                flash(f"Welcome back, {student_data['name']}!", "success")
                return redirect(url_for('dashboard'))
            else:
                if request.is_json:
                    return jsonify({"success": False, "error": msg}), 401
                flash(msg, "danger")
                return render_template('login.html', error=msg, role=role)

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        ok, msg, student_id = auth.register_student(name, email, password, confirm_password)
        if ok:
            if request.is_json:
                return jsonify({"success": True, "message": msg, "redirect": url_for('login_page')})
            flash(msg, "success")
            return redirect(url_for('login_page'))
        else:
            if request.is_json:
                return jsonify({"success": False, "error": msg}), 400
            flash(msg, "danger")
            return render_template('register.html', error=msg, name=name, email=email)

    return render_template('register.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    if request.is_json:
        return jsonify({"success": True, "redirect": url_for('login_page')})
    return redirect(url_for('login_page'))

# ==================== STUDENT DASHBOARD & BROWSING ====================

@app.route('/dashboard')
@auth.student_login_required
def dashboard():
    stats = models.get_library_stats()
    student_id = session['student_id']
    active_loans = models.get_active_transactions_for_student(student_id)
    my_reservations = models.get_reservations_for_student(student_id)
    featured_books = models.get_all_books()[:4]
    
    return render_template(
        'dashboard.html',
        stats=stats,
        active_loans=active_loans,
        my_reservations=my_reservations,
        featured_books=featured_books
    )

@app.route('/books')
def books_catalogue():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', 'all').strip()
    books = models.get_all_books(search_query=query, category=category)
    categories = ["All", "Operating Systems", "Networks", "Databases", "Algorithms"]
    
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({"success": True, "books": [dict(b) for b in books]})

    return render_template(
        'books.html',
        books=books,
        search_query=query,
        selected_category=category,
        categories=categories
    )

@app.route('/books/search')
def books_search_api():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', 'all').strip()
    books = models.get_all_books(search_query=query, category=category)
    return jsonify({"success": True, "count": len(books), "books": [dict(b) for b in books]})

# ==================== ISSUE, RETURN, RESERVATION ACTIONS ====================

@app.route('/issue', methods=['POST'])
@auth.student_login_required
def issue_action():
    data = request.get_json(silent=True) or request.form
    book_id = data.get('book_id')
    student_id = session['student_id']

    if not book_id:
        return jsonify({"success": False, "error": "Book ID is required."}), 400

    result = library.issue_book(book_id=book_id, student_id=student_id, use_lock=True)
    
    if request.is_json:
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    if result['success']:
        flash(result['message'], "success")
    else:
        flash(result['message'], "danger")
    return redirect(request.referrer or url_for('books_catalogue'))

@app.route('/return', methods=['POST'])
@auth.student_login_required
def return_action():
    data = request.get_json(silent=True) or request.form
    copy_id = data.get('copy_id')
    student_id = session['student_id']

    if not copy_id:
        return jsonify({"success": False, "error": "Copy ID is required."}), 400

    result = library.return_book(copy_id=copy_id, student_id=student_id)

    if request.is_json:
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    if result['success']:
        flash(result['message'], "success")
    else:
        flash(result['message'], "danger")
    return redirect(request.referrer or url_for('my_books'))

@app.route('/reserve', methods=['POST'])
@auth.student_login_required
def reserve_action():
    data = request.get_json(silent=True) or request.form
    book_id = data.get('book_id')
    student_id = session['student_id']

    if not book_id:
        return jsonify({"success": False, "error": "Book ID is required."}), 400

    result = library.reserve_book(book_id=book_id, student_id=student_id)

    if request.is_json:
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    if result['success']:
        flash(result['message'], "success")
    else:
        flash(result['message'], "danger")
    return redirect(request.referrer or url_for('books_catalogue'))

@app.route('/reserve/cancel', methods=['POST'])
@auth.student_login_required
def cancel_reservation_action():
    data = request.get_json(silent=True) or request.form
    reservation_id = data.get('reservation_id')
    student_id = session['student_id']

    if not reservation_id:
        return jsonify({"success": False, "error": "Reservation ID is required."}), 400

    result = library.cancel_reservation(reservation_id=int(reservation_id), student_id=student_id)

    if request.is_json:
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

    if result['success']:
        flash(result['message'], "info")
    else:
        flash(result['message'], "danger")
    return redirect(url_for('reservations_page'))

@app.route('/my-books')
@auth.student_login_required
def my_books():
    student_id = session['student_id']
    active_loans = models.get_active_transactions_for_student(student_id)
    history = models.get_all_transactions_for_student(student_id)
    return render_template('my_books.html', active_loans=active_loans, history=history)

@app.route('/reservations')
@auth.student_login_required
def reservations_page():
    student_id = session['student_id']
    reservations = models.get_reservations_for_student(student_id)
    return render_template('reservations.html', reservations=reservations)

# ==================== ADMIN DASHBOARD & BOOK MANAGEMENT ====================

@app.route('/admin')
@auth.admin_required
def admin_dashboard():
    stats = models.get_library_stats()
    books = models.get_all_books()
    students = models.get_all_students()
    transactions = models.get_all_transactions(limit=50)
    reservations = models.get_all_reservations(limit=50)
    
    return render_template(
        'admin.html',
        stats=stats,
        books=books,
        students=students,
        transactions=transactions,
        reservations=reservations
    )

@app.route('/admin/add-book', methods=['POST'])
@auth.admin_required
def admin_add_book():
    data = request.get_json(silent=True) or request.form
    book_id = data.get('book_id', '').strip().upper()
    title = data.get('title', '').strip()
    author = data.get('author', '').strip()
    category = data.get('category', '').strip()
    description = data.get('description', '').strip()
    copies = int(data.get('copies', 1))

    if not book_id or not title or not author or not category:
        msg = "Book ID, Title, Author, and Category are required."
        if request.is_json:
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for('admin_dashboard'))

    existing = models.get_book_by_id(book_id)
    if existing:
        msg = f"A book with ID '{book_id}' already exists."
        if request.is_json:
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for('admin_dashboard'))

    models.create_book(book_id, title, author, category, description, num_copies=copies)
    msg = f"Book '{title}' ({book_id}) with {copies} copies added successfully."
    if request.is_json:
        return jsonify({"success": True, "message": msg})
    flash(msg, "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-copy', methods=['POST'])
@auth.admin_required
def admin_add_copy():
    data = request.get_json(silent=True) or request.form
    book_id = data.get('book_id')
    if not book_id:
        return jsonify({"success": False, "error": "Book ID required"}), 400
    new_cid = models.add_copy_to_book(book_id)
    msg = f"New copy {new_cid} added for book {book_id}."
    if request.is_json:
        return jsonify({"success": True, "message": msg, "copy_id": new_cid})
    flash(msg, "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-book', methods=['POST', 'PUT'])
@auth.admin_required
def admin_update_book():
    data = request.get_json(silent=True) or request.form
    book_id = data.get('book_id')
    title = data.get('title')
    author = data.get('author')
    category = data.get('category')
    description = data.get('description', '')

    if not book_id or not title or not author:
        return jsonify({"success": False, "error": "Missing required fields."}), 400

    models.update_book_details(book_id, title, author, category, description)
    msg = f"Book {book_id} updated successfully."
    if request.is_json:
        return jsonify({"success": True, "message": msg})
    flash(msg, "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-book', methods=['POST', 'DELETE'])
@auth.admin_required
def admin_delete_book():
    data = request.get_json(silent=True) or request.form
    book_id = data.get('book_id')

    if not book_id:
        return jsonify({"success": False, "error": "Book ID is required."}), 400

    ok, msg = models.delete_book(book_id)
    if request.is_json:
        return jsonify({"success": ok, "message" if ok else "error": msg}), 200 if ok else 400
    flash(msg, "success" if ok else "danger")
    return redirect(url_for('admin_dashboard'))

# ==================== OS CONCURRENCY MONITOR ====================

@app.route('/concurrency')
def concurrency_page():
    state = concurrency.get_concurrency_state()
    test_book = models.get_book_by_id("B100")
    test_copies = models.get_copies_for_book("B100") if test_book else []
    return render_template('concurrency.html', initial_state=state, test_book=test_book, test_copies=test_copies)

@app.route('/concurrency-test', methods=['POST'])
def run_concurrency_test_endpoint():
    """
    Executes controlled concurrency demonstration with specified threads and copies.
    Can be invoked with use_mutex=True (safe) or use_mutex=False (demonstrates race condition).
    """
    data = request.get_json(silent=True) or request.form
    num_threads = int(data.get('num_threads', 2))
    initial_copies = int(data.get('initial_copies', 1))
    use_mutex = str(data.get('use_mutex', 'true')).lower() in ('true', '1', 'yes')
    book_id = data.get('book_id', 'B100')

    # Clamp ranges to prevent accidental excessive thread storms
    num_threads = max(1, min(num_threads, 20))
    initial_copies = max(1, min(initial_copies, 10))

    result = concurrency.run_controlled_concurrency_test(
        num_threads=num_threads,
        initial_copies=initial_copies,
        use_mutex=use_mutex,
        book_id=book_id
    )

    return jsonify({"success": True, "data": result})

@app.route('/concurrency-status', methods=['GET'])
def get_concurrency_status_endpoint():
    state = concurrency.get_concurrency_state()
    return jsonify(state)

@app.route('/concurrency-reset', methods=['POST'])
def reset_concurrency_book_endpoint():
    data = request.get_json(silent=True) or request.form
    initial_copies = int(data.get('initial_copies', 1))
    database.reset_concurrency_test_book(initial_copies=initial_copies)
    return jsonify({"success": True, "message": f"Test book reset with {initial_copies} available copy(ies)."})

if __name__ == '__main__':
    print("=" * 70)
    print("OSCN PROJECT 04: LIBRARY BOOK ISSUE & RESERVATION SYSTEM")
    print("Core Implementation: Python, Flask, SQLite, threading.Lock()")
    print("Starting Flask threaded development server on http://127.0.0.1:5000 ...")
    print("=" * 70)
    # Using threaded=True on a single process as required by the specification (Page 4 & 5)
    app.run(host='127.0.0.1', port=5000, debug=True, threaded=True)
