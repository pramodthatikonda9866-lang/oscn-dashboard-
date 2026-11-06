"""
concurrency_demo.py - Complete Python Implementation: Multithreading & Mutex Lock
OSCN Project 04: Library Book Issue & Reservation System

Visibly demonstrates:
1. import threading
2. book_lock = threading.Lock()
3. def issue_book(student_name):
4. with book_lock:
5. Book availability checking logic in SQLite
6. Book issuing logic with status update and transaction
7. students list containing 5 students
8. threads = []
9. threading.Thread(target=issue_book, args=(student,))
10. t.start()
11. t.join()
"""

import threading
import time
import sqlite3
from datetime import datetime

# 1. Initialize Mutex Lock Primitive to protect the shared critical section
book_lock = threading.Lock()

def issue_book(student_name):
    """
    Thread worker function representing an individual student's request.
    Uses 'with book_lock:' to ensure only one thread enters the Critical Section at a time.
    """
    print(f"[{student_name}] Request received. Waiting for Mutex Lock...")

    # 2. Acquire Mutex Lock (Entering Critical Section)
    with book_lock:
        print(f"[{student_name}] Mutex Lock ACQUIRED. Entered Critical Section.")

        # Connect to SQLite Database
        conn = sqlite3.connect("library.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 3. Real Book Availability Checking Logic in SQLite
        print(f"[{student_name}] Checking book availability for 'B100'...")
        cursor.execute(
            "SELECT copy_id FROM book_copies WHERE book_id = 'B100' AND status = 'AVAILABLE' ORDER BY copy_id ASC LIMIT 1"
        )
        available_copy = cursor.fetchone()

        # Simulate disk I/O and processing latency inside the critical section
        time.sleep(0.5)

        # 4. Real Book Issuing Logic
        if available_copy:
            copy_id = available_copy["copy_id"]
            cursor.execute("UPDATE book_copies SET status = 'ISSUED' WHERE copy_id = ?", (copy_id,))
            due_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO transactions (student_id, copy_id, due_date, status) VALUES ((SELECT student_id FROM students LIMIT 1), ?, ?, 'ACTIVE')",
                (copy_id, due_date)
            )
            conn.commit()
            print(f"[{student_name}] SUCCESS: Issued physical copy {copy_id}!")
        else:
            print(f"[{student_name}] REJECTED: Book Unavailable (0 copies left).")

        conn.close()
        print(f"[{student_name}] Releasing Mutex Lock and exiting Critical Section.")

    # Mutex Lock is automatically released here for the next waiting thread

if __name__ == "__main__":
    print("=" * 70)
    print("STARTING 5 CONCURRENT STUDENT REQUESTS DEMONSTRATION")
    print("=" * 70)

    # Reset B100 to 1 available copy for a clean demonstration
    import database
    database.reset_concurrency_test_book(initial_copies=1)

    # 5. List containing 5 students requesting the same book simultaneously
    students = ["Student 1", "Student 2", "Student 3", "Student 4", "Student 5"]

    # 6. List to hold thread objects
    threads = []

    # 7. Create and start threads using threading.Thread
    for student in students:
        t = threading.Thread(target=issue_book, args=(student,))
        threads.append(t)
        t.start()  # Starts thread execution concurrently

    # 8. Wait for all 5 student threads to complete using join()
    for t in threads:
        t.join()  # Coordinator waits until thread t completes

    print("=" * 70)
    print("All 5 student threads finished execution. Mutual exclusion preserved!")
    print("=" * 70)

