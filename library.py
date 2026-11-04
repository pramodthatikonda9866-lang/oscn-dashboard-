"""
library.py - Core Library Business Operations & Rules
Implements book issuing, returning, reserving, and copy status transitions.
All operations coordinate database transactions and mutex synchronization.
"""

from datetime import datetime, timedelta
import time
import threading
from database import get_db_connection

# Shared mutex lock protecting the critical section for book issuing and returning
library_lock = threading.Lock()

def issue_book(book_id: str, student_id: int, use_lock: bool = True, simulate_delay: float = 0.0):
    """
    Issues a copy of the specified book to the given student.
    
    Protected Critical Section:
    1. Check student eligibility (no duplicate active loans for same title).
    2. Check if student has an allocated READY reservation for this book.
    3. If not, select an AVAILABLE physical copy.
    4. Update copy status to ISSUED.
    5. Record active transaction with 14-day due date.
    
    Returns:
        dict: {
            "success": bool,
            "message": str,
            "copy_id": str or None,
            "transaction_id": int or None,
            "thread_event": str
        }
    """
    if use_lock:
        with library_lock:
            return _execute_issue(book_id, student_id, simulate_delay=simulate_delay)
    else:
        # Unsafe execution path for demonstrating race conditions
        return _execute_issue(book_id, student_id, simulate_delay=simulate_delay)

def _execute_issue(book_id: str, student_id: int, simulate_delay: float = 0.0):
    """Internal implementation of the issue critical section."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Duplicate check - Cannot issue same book if student already has active loan
        active_loan = cursor.execute("""
            SELECT t.transaction_id, c.copy_id 
            FROM transactions t
            JOIN book_copies c ON t.copy_id = c.copy_id
            WHERE t.student_id = ? AND c.book_id = ? AND t.status = 'ACTIVE'
        """, (student_id, book_id)).fetchone()

        if active_loan:
            conn.close()
            return {
                "success": False,
                "message": f"Duplicate request: You already have an active loan for book {book_id} (Copy {active_loan['copy_id']}).",
                "copy_id": None,
                "transaction_id": None,
                "thread_event": "DUPLICATE_REJECTED"
            }

        # Step 2: Check if this student has a READY reservation holding a copy
        ready_reservation = cursor.execute("""
            SELECT reservation_id, allocated_copy_id 
            FROM reservations
            WHERE student_id = ? AND book_id = ? AND status = 'READY'
            ORDER BY reservation_id ASC LIMIT 1
        """, (student_id, book_id)).fetchone()

        chosen_copy_id = None
        reservation_id_to_complete = None

        if ready_reservation and ready_reservation['allocated_copy_id']:
            chosen_copy_id = ready_reservation['allocated_copy_id']
            reservation_id_to_complete = ready_reservation['reservation_id']
        else:
            # Step 3: Find first available copy
            available_copy = cursor.execute("""
                SELECT copy_id FROM book_copies 
                WHERE book_id = ? AND status = 'AVAILABLE'
                ORDER BY copy_id ASC LIMIT 1
            """, (book_id,)).fetchone()

            if not available_copy:
                conn.close()
                return {
                    "success": False,
                    "message": f"No physical copies of book {book_id} are currently available. Please place a reservation.",
                    "copy_id": None,
                    "transaction_id": None,
                    "thread_event": "NO_COPY_AVAILABLE"
                }
            chosen_copy_id = available_copy['copy_id']

        # Simulating processing / context switch window to demonstrate race condition when unlocked
        if simulate_delay > 0:
            time.sleep(simulate_delay)

        # Step 4: Update copy status to ISSUED
        cursor.execute("UPDATE book_copies SET status = 'ISSUED' WHERE copy_id = ?", (chosen_copy_id,))

        # If fulfilled via reservation, mark reservation COMPLETED
        if reservation_id_to_complete:
            cursor.execute("UPDATE reservations SET status = 'COMPLETED' WHERE reservation_id = ?", (reservation_id_to_complete,))

        # Step 5: Record transaction
        due_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO transactions (student_id, copy_id, due_date, status)
            VALUES (?, ?, ?, 'ACTIVE')
        """, (student_id, chosen_copy_id, due_date))
        transaction_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"Book successfully issued! Copy ID: {chosen_copy_id}. Due on: {due_date}.",
            "copy_id": chosen_copy_id,
            "transaction_id": transaction_id,
            "thread_event": "ISSUE_SUCCESS"
        }

    except Exception as e:
        conn.rollback()
        conn.close()
        return {
            "success": False,
            "message": f"Transaction failed: {str(e)}",
            "copy_id": None,
            "transaction_id": None,
            "thread_event": "TRANSACTION_ERROR"
        }

def return_book(copy_id: str, student_id: int):
    """
    Safely processes the return of an issued book copy.
    Validates student ownership and updates reservation queue according to policy.
    
    Reservation Allocation Policy:
    When a copy is returned and a waiting reservation exists for this title,
    allocate that copy to the earliest waiting student, set status to READY
    with a 48-hour pickup deadline, and set copy status to RESERVED.
    Otherwise, mark copy AVAILABLE.
    """
    with library_lock:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 1. Validate active loan and ownership
            active_tx = cursor.execute("""
                SELECT t.transaction_id, t.copy_id, c.book_id
                FROM transactions t
                JOIN book_copies c ON t.copy_id = c.copy_id
                WHERE t.copy_id = ? AND t.student_id = ? AND t.status = 'ACTIVE'
            """, (copy_id, student_id)).fetchone()

            if not active_tx:
                conn.close()
                return {
                    "success": False,
                    "message": f"Return rejected: You do not have an active loan record for copy {copy_id}."
                }

            book_id = active_tx['book_id']
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 2. Mark active transaction as RETURNED
            cursor.execute("""
                UPDATE transactions 
                SET status = 'RETURNED', return_date = ? 
                WHERE transaction_id = ?
            """, (now_str, active_tx['transaction_id']))

            # 3. Check reservation queue for this book
            waiting_res = cursor.execute("""
                SELECT reservation_id, student_id 
                FROM reservations
                WHERE book_id = ? AND status = 'WAITING'
                ORDER BY queue_number ASC, reservation_date ASC
                LIMIT 1
            """, (book_id,)).fetchone()

            if waiting_res:
                # Policy: Allocate returned copy to earliest waiting student
                deadline = (datetime.now() + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    UPDATE reservations 
                    SET status = 'READY', allocated_copy_id = ?, pickup_deadline = ?
                    WHERE reservation_id = ?
                """, (copy_id, deadline, waiting_res['reservation_id']))

                # Copy is marked RESERVED for that student
                cursor.execute("UPDATE book_copies SET status = 'RESERVED' WHERE copy_id = ?", (copy_id,))
                status_msg = f"Copy {copy_id} returned successfully and automatically allocated to Student #{waiting_res['student_id']} (Reservation #{waiting_res['reservation_id']})."
            else:
                # No waiting reservations: copy becomes AVAILABLE
                cursor.execute("UPDATE book_copies SET status = 'AVAILABLE' WHERE copy_id = ?", (copy_id,))
                status_msg = f"Copy {copy_id} returned successfully and is now AVAILABLE."

            conn.commit()
            conn.close()

            return {
                "success": True,
                "message": status_msg
            }

        except Exception as e:
            conn.rollback()
            conn.close()
            return {
                "success": False,
                "message": f"Error processing return: {str(e)}"
            }

def reserve_book(book_id: str, student_id: int):
    """
    Places a student into the ordered reservation queue for a book.
    """
    with library_lock:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Check book existence
            book = cursor.execute("SELECT book_id, title FROM books WHERE book_id = ?", (book_id,)).fetchone()
            if not book:
                conn.close()
                return {"success": False, "message": "Book not found."}

            # Check if student already has active loan of this book
            has_loan = cursor.execute("""
                SELECT t.transaction_id FROM transactions t
                JOIN book_copies c ON t.copy_id = c.copy_id
                WHERE t.student_id = ? AND c.book_id = ? AND t.status = 'ACTIVE'
            """, (student_id, book_id)).fetchone()

            if has_loan:
                conn.close()
                return {"success": False, "message": "You already have an active loan for this book title."}

            # Check if student already has an active reservation
            existing_res = cursor.execute("""
                SELECT reservation_id, status FROM reservations
                WHERE student_id = ? AND book_id = ? AND status IN ('WAITING', 'READY')
            """, (student_id, book_id)).fetchone()

            if existing_res:
                conn.close()
                return {"success": False, "message": f"You already have an active reservation (#{existing_res['reservation_id']}) with status: {existing_res['status']}."}

            # Determine next queue position
            max_q = cursor.execute("""
                SELECT COALESCE(MAX(queue_number), 0) as max_queue 
                FROM reservations 
                WHERE book_id = ? AND status = 'WAITING'
            """, (book_id,)).fetchone()['max_queue']

            new_queue_num = max_q + 1

            cursor.execute("""
                INSERT INTO reservations (student_id, book_id, queue_number, status)
                VALUES (?, ?, ?, 'WAITING')
            """, (student_id, book_id, new_queue_num))
            res_id = cursor.lastrowid

            conn.commit()
            conn.close()

            return {
                "success": True,
                "message": f"Reservation confirmed! Your queue position is #{new_queue_num} for '{book['title']}'.",
                "queue_number": new_queue_num,
                "reservation_id": res_id
            }

        except Exception as e:
            conn.rollback()
            conn.close()
            return {"success": False, "message": f"Reservation failed: {str(e)}"}

def cancel_reservation(reservation_id: int, student_id: int = None):
    """
    Cancels an existing reservation. If it had an allocated copy, frees the copy
    or reallocates it to the next waiting reservation.
    """
    with library_lock:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            query = "SELECT * FROM reservations WHERE reservation_id = ?"
            params = [reservation_id]
            if student_id:
                query += " AND student_id = ?"
                params.append(student_id)

            res = cursor.execute(query, params).fetchone()
            if not res:
                conn.close()
                return {"success": False, "message": "Reservation record not found or not owned by you."}

            if res['status'] not in ('WAITING', 'READY'):
                conn.close()
                return {"success": False, "message": f"Cannot cancel reservation with status '{res['status']}'."}

            book_id = res['book_id']
            allocated_copy = res['allocated_copy_id']

            # Mark this reservation cancelled
            cursor.execute("UPDATE reservations SET status = 'CANCELLED' WHERE reservation_id = ?", (reservation_id,))

            # If a copy was already held for this reservation, reallocate or free it
            if allocated_copy:
                next_waiter = cursor.execute("""
                    SELECT reservation_id, student_id FROM reservations
                    WHERE book_id = ? AND status = 'WAITING'
                    ORDER BY queue_number ASC, reservation_date ASC LIMIT 1
                """, (book_id,)).fetchone()

                if next_waiter:
                    deadline = (datetime.now() + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("""
                        UPDATE reservations SET status = 'READY', allocated_copy_id = ?, pickup_deadline = ?
                        WHERE reservation_id = ?
                    """, (allocated_copy, deadline, next_waiter['reservation_id']))
                else:
                    cursor.execute("UPDATE book_copies SET status = 'AVAILABLE' WHERE copy_id = ?", (allocated_copy,))

            # Renumber remaining waiting queue for this book
            waiting_list = cursor.execute("""
                SELECT reservation_id FROM reservations
                WHERE book_id = ? AND status = 'WAITING'
                ORDER BY queue_number ASC, reservation_date ASC
            """, (book_id,)).fetchall()

            for idx, w in enumerate(waiting_list, start=1):
                cursor.execute("UPDATE reservations SET queue_number = ? WHERE reservation_id = ?", (idx, w['reservation_id']))

            conn.commit()
            conn.close()
            return {"success": True, "message": "Reservation cancelled successfully."}

        except Exception as e:
            conn.rollback()
            conn.close()
            return {"success": False, "message": f"Error cancelling reservation: {str(e)}"}

