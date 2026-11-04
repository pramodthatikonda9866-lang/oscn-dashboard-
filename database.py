"""
database.py - Database Connection and Schema Management for OSCN Project 04
Library Book Issue & Reservation System

Features:
- SQLite connection management with row_factory=sqlite3.Row
- Foreign key constraint enforcement (PRAGMA foreign_keys = ON)
- Schema creation and seed data initialization
- Helper to reset dedicated concurrency test book
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_NAME = "library.db"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)

def get_db_connection():
    """
    Creates and returns a SQLite database connection with row factory enabled
    and foreign key constraints strictly enforced.
    """
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(seed=True):
    """
    Initializes database tables and optionally seeds default students,
    admins, books, and copies.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Students Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        student_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Admins Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );
    """)

    # 3. Books Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        book_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        cover_image TEXT
    );
    """)

    # 4. Book Copies Table (Tracks physical copies individually)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS book_copies (
        copy_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('AVAILABLE', 'ISSUED', 'RESERVED')) DEFAULT 'AVAILABLE',
        FOREIGN KEY (book_id) REFERENCES books (book_id) ON DELETE CASCADE
    );
    """)

    # 5. Transactions Table (Issue & Return History)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        copy_id TEXT NOT NULL,
        issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        due_date TIMESTAMP NOT NULL,
        return_date TIMESTAMP,
        status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'RETURNED')) DEFAULT 'ACTIVE',
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (copy_id) REFERENCES book_copies (copy_id)
    );
    """)

    # 6. Reservations Table (Ordered waiting list and lifecycle)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        book_id TEXT NOT NULL,
        reservation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        queue_number INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('WAITING', 'READY', 'COMPLETED', 'CANCELLED')) DEFAULT 'WAITING',
        allocated_copy_id TEXT,
        pickup_deadline TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (book_id) REFERENCES books (book_id),
        FOREIGN KEY (allocated_copy_id) REFERENCES book_copies (copy_id)
    );
    """)

    conn.commit()

    if seed:
        seed_initial_data(conn)

    conn.close()

def seed_initial_data(conn):
    """
    Seeds initial administrator, students, books, and physical copies.
    """
    cursor = conn.cursor()

    # Seed Admin
    cursor.execute("SELECT COUNT(*) as count FROM admins WHERE username = 'admin'")
    if cursor.fetchone()['count'] == 0:
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ('admin', generate_password_hash('admin123'))
        )
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ('librarian', generate_password_hash('librarian123'))
        )

    # Seed Students
    cursor.execute("SELECT COUNT(*) as count FROM students")
    if cursor.fetchone()['count'] == 0:
        initial_students = [
            ("John Doe", "john@university.edu", "student123"),
            ("Alice Smith", "alice@university.edu", "student123"),
            ("Bob Johnson", "bob@university.edu", "student123"),
            ("Charlie Brown", "charlie@university.edu", "student123"),
            ("Diana Prince", "diana@university.edu", "student123"),
        ]
        for name, email, pwd in initial_students:
            cursor.execute(
                "INSERT INTO students (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(pwd))
            )

    # Seed Books & Copies
    cursor.execute("SELECT COUNT(*) as count FROM books")
    if cursor.fetchone()['count'] == 0:
        sample_books = [
            {
                "id": "B100",
                "title": "Operating System Concepts (Demo Book)",
                "author": "Abraham Silberschatz & Peter B. Galvin",
                "category": "Operating Systems",
                "desc": "Official benchmark book used for classroom concurrency, race condition, and mutex lock demonstrations.",
                "cover": "os_concepts.jpg",
                "copies": 1  # 1 copy by default to demonstrate race conditions when 2+ students request
            },
            {
                "id": "B101",
                "title": "Modern Operating Systems",
                "author": "Andrew S. Tanenbaum & Herbert Bos",
                "category": "Operating Systems",
                "desc": "In-depth treatment of processes, threads, synchronization, memory management, and file systems.",
                "cover": "modern_os.jpg",
                "copies": 3
            },
            {
                "id": "B102",
                "title": "Computer Networks: A Systems Approach",
                "author": "Larry L. Peterson & Bruce S. Davie",
                "category": "Networks",
                "desc": "Explores the principles of computer networking, layered architectures, and communication protocols.",
                "cover": "computer_networks.jpg",
                "copies": 2
            },
            {
                "id": "B103",
                "title": "Database System Concepts",
                "author": "Abraham Silberschatz, Henry F. Korth",
                "category": "Databases",
                "desc": "Fundamental concepts of relational databases, SQL, ACID transactions, and concurrency control.",
                "cover": "database_concepts.jpg",
                "copies": 2
            },
            {
                "id": "B104",
                "title": "Introduction to Algorithms",
                "author": "Thomas H. Cormen, Charles E. Leiserson",
                "category": "Algorithms",
                "desc": "Comprehensive reference covering sorting, graph algorithms, dynamic programming, and complexity.",
                "cover": "algorithms.jpg",
                "copies": 1  # 1 copy to easily test reservation queue
            },
            {
                "id": "B105",
                "title": "Operating Systems: Three Easy Pieces",
                "author": "Remzi H. Arpaci-Dusseau",
                "category": "Operating Systems",
                "desc": "Covers Virtualization, Concurrency, and Persistence with practical C and thread programming examples.",
                "cover": "ostep.jpg",
                "copies": 2
            }
        ]

        for b in sample_books:
            cursor.execute(
                "INSERT INTO books (book_id, title, author, category, description, cover_image) VALUES (?, ?, ?, ?, ?, ?)",
                (b["id"], b["title"], b["author"], b["category"], b["desc"], b["cover"])
            )
            for copy_idx in range(1, b["copies"] + 1):
                copy_id = f"{b['id']}-C{copy_idx:03d}"
                cursor.execute(
                    "INSERT INTO book_copies (copy_id, book_id, status) VALUES (?, ?, 'AVAILABLE')",
                    (copy_id, b["id"])
                )

    conn.commit()

def reset_concurrency_test_book(initial_copies=1):
    """
    Resets the dedicated concurrency test book (B100) to a clean state
    with exactly the specified number of available copies.
    Cancels any active transactions or reservations for B100.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete existing transactions for copies of B100
    cursor.execute("""
        DELETE FROM transactions 
        WHERE copy_id IN (SELECT copy_id FROM book_copies WHERE book_id = 'B100')
    """)

    # Delete existing reservations for B100
    cursor.execute("DELETE FROM reservations WHERE book_id = 'B100'")

    # Delete old copies of B100
    cursor.execute("DELETE FROM book_copies WHERE book_id = 'B100'")

    # Ensure book B100 exists
    cursor.execute("SELECT book_id FROM books WHERE book_id = 'B100'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO books (book_id, title, author, category, description, cover_image) VALUES (?, ?, ?, ?, ?, ?)",
            ('B100', 'Operating System Concepts (Demo Book)', 'Abraham Silberschatz & Peter B. Galvin',
             'Operating Systems', 'Official benchmark book used for concurrency demonstrations.', 'os_concepts.jpg')
        )

    # Re-insert fresh available copies
    for i in range(1, initial_copies + 1):
        copy_id = f"B100-C{i:03d}"
        cursor.execute(
            "INSERT INTO book_copies (copy_id, book_id, status) VALUES (?, ?, 'AVAILABLE')",
            (copy_id, 'B100')
        )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
