"""
models.py - Data Access Layer for Library Management System
Provides functions to interact with students, admins, books, copies,
transactions, and reservations in SQLite.
"""

from datetime import datetime, timedelta
from database import get_db_connection

# ==================== STUDENT HELPERS ====================

def get_student_by_id(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    conn.close()
    return student

def get_student_by_email(email):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
    conn.close()
    return student

def create_student(name, email, password_hash):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO students (name, email, password_hash) VALUES (?, ?, ?)",
        (name.strip(), email.strip().lower(), password_hash)
    )
    student_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return student_id

def get_all_students():
    conn = get_db_connection()
    students = conn.execute("SELECT student_id, name, email, created_at FROM students ORDER BY student_id ASC").fetchall()
    conn.close()
    return students

# ==================== ADMIN HELPERS ====================

def get_admin_by_username(username):
    conn = get_db_connection()
    admin = conn.execute("SELECT * FROM admins WHERE LOWER(username) = LOWER(?)", (username.strip(),)).fetchone()
    conn.close()
    return admin

def get_admin_by_id(admin_id):
    conn = get_db_connection()
    admin = conn.execute("SELECT * FROM admins WHERE admin_id = ?", (admin_id,)).fetchone()
    conn.close()
    return admin

# ==================== BOOK & COPY HELPERS ====================

def get_all_books(search_query=None, category=None):
    """
    Returns books with dynamic counts of total copies, available copies,
    and active reservations.
    """
    conn = get_db_connection()
    sql = """
    SELECT 
        b.book_id, b.title, b.author, b.category, b.description, b.cover_image,
        COUNT(c.copy_id) AS total_copies,
        SUM(CASE WHEN c.status = 'AVAILABLE' THEN 1 ELSE 0 END) AS available_copies,
        SUM(CASE WHEN c.status = 'ISSUED' THEN 1 ELSE 0 END) AS issued_copies,
        SUM(CASE WHEN c.status = 'RESERVED' THEN 1 ELSE 0 END) AS reserved_copies,
        (SELECT COUNT(*) FROM reservations r WHERE r.book_id = b.book_id AND r.status = 'WAITING') AS waiting_reservations
    FROM books b
    LEFT JOIN book_copies c ON b.book_id = c.book_id
    WHERE 1=1
    """
    params = []
    if search_query:
        q = f"%{search_query.strip()}%"
        sql += " AND (b.title LIKE ? OR b.author LIKE ? OR b.book_id LIKE ? OR b.description LIKE ?)"
        params.extend([q, q, q, q])
    if category and category.lower() != 'all':
        sql += " AND LOWER(b.category) = LOWER(?)"
        params.append(category.strip())

    sql += " GROUP BY b.book_id ORDER BY b.book_id ASC"
    books = conn.execute(sql, params).fetchall()
    conn.close()
    return books

def get_book_by_id(book_id):
    conn = get_db_connection()
    book = conn.execute("""
    SELECT 
        b.book_id, b.title, b.author, b.category, b.description, b.cover_image,
        COUNT(c.copy_id) AS total_copies,
        SUM(CASE WHEN c.status = 'AVAILABLE' THEN 1 ELSE 0 END) AS available_copies,
        SUM(CASE WHEN c.status = 'ISSUED' THEN 1 ELSE 0 END) AS issued_copies,
        SUM(CASE WHEN c.status = 'RESERVED' THEN 1 ELSE 0 END) AS reserved_copies
    FROM books b
    LEFT JOIN book_copies c ON b.book_id = c.book_id
    WHERE b.book_id = ?
    GROUP BY b.book_id
    """, (book_id,)).fetchone()
    conn.close()
    return book

def get_copies_for_book(book_id):
    conn = get_db_connection()
    copies = conn.execute("SELECT * FROM book_copies WHERE book_id = ? ORDER BY copy_id ASC", (book_id,)).fetchall()
    conn.close()
    return copies

def get_copy_by_id(copy_id):
    conn = get_db_connection()
    copy = conn.execute("SELECT * FROM book_copies WHERE copy_id = ?", (copy_id,)).fetchone()
    conn.close()
    return copy

def create_book(book_id, title, author, category, description="", cover_image="default.jpg", num_copies=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO books (book_id, title, author, category, description, cover_image) VALUES (?, ?, ?, ?, ?, ?)",
        (book_id.strip().upper(), title.strip(), author.strip(), category.strip(), description.strip(), cover_image)
    )
    for i in range(1, num_copies + 1):
        copy_id = f"{book_id.strip().upper()}-C{i:03d}"
        cursor.execute(
            "INSERT INTO book_copies (copy_id, book_id, status) VALUES (?, ?, 'AVAILABLE')",
            (copy_id, book_id.strip().upper())
        )
    conn.commit()
    conn.close()

def add_copy_to_book(book_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Find max copy index
    existing = cursor.execute("SELECT copy_id FROM book_copies WHERE book_id = ?", (book_id,)).fetchall()
    max_idx = 0
    for row in existing:
        cid = row['copy_id']
        parts = cid.split('-C')
        if len(parts) == 2 and parts[1].isdigit():
            max_idx = max(max_idx, int(parts[1]))
    new_idx = max_idx + 1
    new_copy_id = f"{book_id}-C{new_idx:03d}"
    cursor.execute("INSERT INTO book_copies (copy_id, book_id, status) VALUES (?, ?, 'AVAILABLE')", (new_copy_id, book_id))
    conn.commit()
    conn.close()
    return new_copy_id

def update_book_details(book_id, title, author, category, description):
    conn = get_db_connection()
    conn.execute(
        "UPDATE books SET title = ?, author = ?, category = ?, description = ? WHERE book_id = ?",
        (title.strip(), author.strip(), category.strip(), description.strip(), book_id)
    )
    conn.commit()
    conn.close()

def delete_book(book_id):
    """
    Deletes a book only if none of its copies are currently issued.
    Returns (success: bool, message: str)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if any copy is issued or reserved
    active_copies = cursor.execute(
        "SELECT COUNT(*) as count FROM book_copies WHERE book_id = ? AND status IN ('ISSUED', 'RESERVED')",
        (book_id,)
    ).fetchone()['count']
    if active_copies > 0:
        conn.close()
        return False, "Cannot delete book while copies are currently issued or reserved."

    # Delete book copies first or let cascade delete
    cursor.execute("DELETE FROM book_copies WHERE book_id = ?", (book_id,))
    cursor.execute("DELETE FROM reservations WHERE book_id = ?", (book_id,))
    cursor.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
    conn.commit()
    conn.close()
    return True, "Book deleted successfully."

# ==================== TRANSACTION HELPERS ====================

def get_active_transactions_for_student(student_id):
    conn = get_db_connection()
    loans = conn.execute("""
    SELECT 
        t.transaction_id, t.student_id, t.copy_id, t.issue_date, t.due_date, t.status,
        b.book_id, b.title, b.author, b.category, b.cover_image
    FROM transactions t
    JOIN book_copies c ON t.copy_id = c.copy_id
    JOIN books b ON c.book_id = b.book_id
    WHERE t.student_id = ? AND t.status = 'ACTIVE'
    ORDER BY t.issue_date DESC
    """, (student_id,)).fetchall()
    conn.close()
    return loans

def get_all_transactions_for_student(student_id):
    conn = get_db_connection()
    history = conn.execute("""
    SELECT 
        t.transaction_id, t.student_id, t.copy_id, t.issue_date, t.due_date, t.return_date, t.status,
        b.book_id, b.title, b.author, b.category
    FROM transactions t
    JOIN book_copies c ON t.copy_id = c.copy_id
    JOIN books b ON c.book_id = b.book_id
    WHERE t.student_id = ?
    ORDER BY t.transaction_id DESC
    """, (student_id,)).fetchall()
    conn.close()
    return history

def get_all_transactions(limit=100):
    conn = get_db_connection()
    txs = conn.execute("""
    SELECT 
        t.transaction_id, t.student_id, s.name as student_name, s.email as student_email,
        t.copy_id, t.issue_date, t.due_date, t.return_date, t.status,
        b.book_id, b.title as book_title
    FROM transactions t
    JOIN students s ON t.student_id = s.student_id
    JOIN book_copies c ON t.copy_id = c.copy_id
    JOIN books b ON c.book_id = b.book_id
    ORDER BY t.transaction_id DESC
    LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return txs

# ==================== RESERVATION HELPERS ====================

def get_reservations_for_student(student_id):
    conn = get_db_connection()
    reservations = conn.execute("""
    SELECT 
        r.reservation_id, r.student_id, r.book_id, r.reservation_date, r.queue_number, r.status,
        r.allocated_copy_id, r.pickup_deadline,
        b.title as book_title, b.author as book_author, b.category
    FROM reservations r
    JOIN books b ON r.book_id = b.book_id
    WHERE r.student_id = ?
    ORDER BY r.reservation_id DESC
    """, (student_id,)).fetchall()
    conn.close()
    return reservations

def get_all_reservations(limit=100):
    conn = get_db_connection()
    reservations = conn.execute("""
    SELECT 
        r.reservation_id, r.student_id, s.name as student_name, s.email as student_email,
        r.book_id, b.title as book_title, r.reservation_date, r.queue_number, r.status,
        r.allocated_copy_id, r.pickup_deadline
    FROM reservations r
    JOIN students s ON r.student_id = s.student_id
    JOIN books b ON r.book_id = b.book_id
    ORDER BY r.reservation_id DESC
    LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return reservations

# ==================== STATS ====================

def get_library_stats():
    conn = get_db_connection()
    total_books = conn.execute("SELECT COUNT(*) as c FROM books").fetchone()['c']
    total_copies = conn.execute("SELECT COUNT(*) as c FROM book_copies").fetchone()['c']
    available_copies = conn.execute("SELECT COUNT(*) as c FROM book_copies WHERE status = 'AVAILABLE'").fetchone()['c']
    issued_copies = conn.execute("SELECT COUNT(*) as c FROM book_copies WHERE status = 'ISSUED'").fetchone()['c']
    active_reservations = conn.execute("SELECT COUNT(*) as c FROM reservations WHERE status IN ('WAITING', 'READY')").fetchone()['c']
    total_students = conn.execute("SELECT COUNT(*) as c FROM students").fetchone()['c']
    
    recent_transactions = conn.execute("""
    SELECT 
        t.transaction_id, s.name as student_name, b.title as book_title, t.copy_id,
        t.issue_date, t.return_date, t.status
    FROM transactions t
    JOIN students s ON t.student_id = s.student_id
    JOIN book_copies c ON t.copy_id = c.copy_id
    JOIN books b ON c.book_id = b.book_id
    ORDER BY t.transaction_id DESC
    LIMIT 6
    """).fetchall()

    conn.close()
    return {
        "total_books": total_books,
        "total_copies": total_copies,
        "available_copies": available_copies,
        "issued_copies": issued_copies,
        "active_reservations": active_reservations,
        "total_students": total_students,
        "recent_transactions": recent_transactions
    }

