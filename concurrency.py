"""
concurrency.py - Multithreading, Mutex Synchronization & Concurrency Monitor
Implements real Python thread spawning, threading.Lock() mutual exclusion,
barrier synchronization, event sequence logging, and controlled test execution.
Directly integrates with the real library book issue system and models.
"""

import threading
import time
from datetime import datetime
from database import get_db_connection, reset_concurrency_test_book
import models
import library

# Reuse the unified mutex from library.py to avoid duplicate mutexes
concurrency_mutex = library.library_lock
book_lock = concurrency_mutex

def issue_book(student_name: str, book_id: str = "B100"):
    """
    Core Mutex-Protected Issue Operation:
    Checks SQLite for an available copy, marks it ISSUED, and records the active transaction.
    Guaranteed mutual exclusion using 'with book_lock:'.
    """
    with book_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # 1. Check availability
            cursor.execute(
                "SELECT copy_id FROM book_copies WHERE book_id = ? AND status = 'AVAILABLE' ORDER BY copy_id ASC LIMIT 1",
                (book_id,)
            )
            available_copy = cursor.fetchone()
            time.sleep(0.04)  # Processing latency inside critical section
            
            if available_copy:
                copy_id = available_copy['copy_id']
                cursor.execute("UPDATE book_copies SET status = 'ISSUED' WHERE copy_id = ?", (copy_id,))
                due_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO transactions (student_id, copy_id, due_date, status) VALUES ((SELECT student_id FROM students LIMIT 1), ?, ?, 'ACTIVE')",
                    (copy_id, due_date)
                )
                conn.commit()
                return {"success": True, "copy_id": copy_id, "message": f"Book Issued: {copy_id}"}
            else:
                return {"success": False, "copy_id": None, "message": "Book Unavailable"}
        finally:
            conn.close()

# Thread-safe event logging structures
_event_log_lock = threading.Lock()
_global_event_seq = 0
current_test_events = []
current_test_status = {
    "is_running": False,
    "lock_state": "UNLOCKED",
    "lock_holder": None,
    "total_threads": 5,
    "initial_copies": 1,
    "successful_issues": 0,
    "failed_requests": 0,
    "mutex_enabled": True,
    "invariants_passed": True,
    "summary_message": "Ready to run concurrency demonstration.",
    "student_threads": []
}

def log_event(thread_id: int, thread_name: str, event_type: str, details: str = "", status_badge: str = "WAITING"):
    """
    Safely appends a real-time event to the concurrency monitor log.
    Includes monotonically increasing sequence number and millisecond timestamp.
    """
    global _global_event_seq
    with _event_log_lock:
        _global_event_seq += 1
        now_ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        event_record = {
            "seq": _global_event_seq,
            "timestamp": now_ts,
            "thread_id": thread_id,
            "thread_name": thread_name,
            "event_type": event_type,
            "details": details,
            "status_badge": status_badge
        }
        current_test_events.append(event_record)
        return event_record

def get_concurrency_state():
    """Returns the current state and snapshot of all logged test events."""
    with _event_log_lock:
        return {
            "status": dict(current_test_status),
            "events": list(current_test_events)
        }

def _worker_thread_task(
    thread_idx: int,
    student_id: int,
    student_name: str,
    book_id: str,
    use_mutex: bool,
    start_barrier: threading.Barrier,
    results_dict: dict
):
    """
    Worker thread representing an individual student's concurrent request.
    Follows the exact lifecycle required:
    1. Student Thread Created
    2. Thread Started
    3. Waiting for Mutex
    4. Mutex Acquired
    5. Entering Critical Section
    6. Checking Book Availability
    7. Book Issued / Unavailable
    8. Mutex Released
    9. Thread Completed
    """
    thread_name = f"Student {thread_idx} ({student_name})"

    # Initialize thread state
    results_dict[thread_idx] = {
        "thread_idx": thread_idx,
        "student_name": student_name,
        "student_id": student_id,
        "status": "WAITING",
        "current_step": "Thread Started",
        "copy_id": None
    }

    # Barrier Synchronization: Ensures all student threads arrive and start together
    start_barrier.wait()

    # Step 2: Thread Started
    log_event(thread_idx, thread_name, "THREAD_STARTED", f"Student requested to issue book '{book_id}'", "RUNNING")
    results_dict[thread_idx]["current_step"] = "Waiting for Mutex"

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if use_mutex:
            # Step 3: Waiting for Mutex
            log_event(thread_idx, thread_name, "WAITING_FOR_MUTEX", "Thread waiting to acquire Mutex Lock...", "WAITING")
            results_dict[thread_idx]["status"] = "WAITING"
            results_dict[thread_idx]["current_step"] = "Waiting for Mutex"

            # Step 4: Mutex Acquired
            concurrency_mutex.acquire()
            current_test_status["lock_state"] = "LOCKED"
            current_test_status["lock_holder"] = thread_name

            log_event(thread_idx, thread_name, "MUTEX_ACQUIRED", "Mutex Lock Acquired. Mutual exclusion active.", "LOCKED")
            results_dict[thread_idx]["status"] = "LOCKED"
            results_dict[thread_idx]["current_step"] = "Mutex Acquired"

            # Step 5: Entering Critical Section
            log_event(thread_idx, thread_name, "ENTERED_CRITICAL_SECTION", "Entered Critical Section: accessing shared SQLite book_copies", "LOCKED")
            results_dict[thread_idx]["current_step"] = "In Critical Section"

            # Step 6: Checking Book Availability
            log_event(thread_idx, thread_name, "CHECKING_AVAILABILITY", f"Querying SQLite for available copy of '{book_id}'...", "RUNNING")
            results_dict[thread_idx]["current_step"] = "Checking Book Availability"

            available_copy = cursor.execute("""
                SELECT copy_id FROM book_copies 
                WHERE book_id = ? AND status = 'AVAILABLE' 
                ORDER BY copy_id ASC LIMIT 1
            """, (book_id,)).fetchone()

            # Small realistic latency gap inside critical section
            time.sleep(0.04)

            # Step 7: Book Issued / Book Unavailable
            if available_copy:
                copy_id = available_copy['copy_id']
                cursor.execute("UPDATE book_copies SET status = 'ISSUED' WHERE copy_id = ?", (copy_id,))
                
                due_date = (datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO transactions (student_id, copy_id, due_date, status)
                    VALUES (?, ?, ?, 'ACTIVE')
                """, (student_id, copy_id, due_date))
                conn.commit()

                log_event(thread_idx, thread_name, "BOOK_ISSUED", f"SUCCESS: Physical copy {copy_id} issued! Transaction recorded.", "COMPLETED")
                results_dict[thread_idx]["status"] = "COMPLETED"
                results_dict[thread_idx]["current_step"] = f"Book Issued ({copy_id})"
                results_dict[thread_idx]["copy_id"] = copy_id
            else:
                log_event(thread_idx, thread_name, "BOOK_UNAVAILABLE", "REJECTED: Book Unavailable. All copies currently issued.", "FAILED")
                results_dict[thread_idx]["status"] = "FAILED"
                results_dict[thread_idx]["current_step"] = "Book Unavailable (0 copies left)"

            # Step 8: Mutex Released
            current_test_status["lock_state"] = "UNLOCKED"
            current_test_status["lock_holder"] = None
            concurrency_mutex.release()
            log_event(thread_idx, thread_name, "MUTEX_RELEASED", "Released Mutex Lock. Exited Critical Section.", "RUNNING")

        else:
            # UNSAFE EXECUTION PATH (NO MUTEX - DEMONSTRATES RACE CONDITION ON ISOLATED TEST DATA)
            log_event(thread_idx, thread_name, "NO_MUTEX_WARNING", "WARNING: Mutex Lock Disabled! Entering unprotected critical section.", "RUNNING")
            results_dict[thread_idx]["status"] = "RUNNING"
            results_dict[thread_idx]["current_step"] = "Unprotected Access (No Lock)"

            # Multiple threads read at the exact same moment without lock
            available_copy = cursor.execute("""
                SELECT copy_id FROM book_copies 
                WHERE book_id = ? AND status = 'AVAILABLE' 
                ORDER BY copy_id ASC LIMIT 1
            """, (book_id,)).fetchone()

            # Latency gap: allows competing threads to observe the same copy as AVAILABLE!
            time.sleep(0.06)

            if available_copy:
                copy_id = available_copy['copy_id']
                cursor.execute("UPDATE book_copies SET status = 'ISSUED' WHERE copy_id = ?", (copy_id,))
                cursor.execute("""
                    INSERT INTO transactions (student_id, copy_id, due_date, status)
                    VALUES (?, ?, datetime('now', '+14 days'), 'ACTIVE')
                """, (student_id, copy_id))
                conn.commit()

                log_event(thread_idx, thread_name, "BOOK_ISSUED (RACE)", f"Unsafely assigned copy {copy_id}! (Collision)", "COMPLETED")
                results_dict[thread_idx]["status"] = "COMPLETED"
                results_dict[thread_idx]["current_step"] = f"Issued {copy_id} (Race Collision!)"
                results_dict[thread_idx]["copy_id"] = copy_id
            else:
                log_event(thread_idx, thread_name, "BOOK_UNAVAILABLE", "Observed 0 available copies.", "FAILED")
                results_dict[thread_idx]["status"] = "FAILED"
                results_dict[thread_idx]["current_step"] = "Book Unavailable"

        # Step 9: Thread Completed
        log_event(thread_idx, thread_name, "THREAD_COMPLETED", "Student thread operation completed.", results_dict[thread_idx]["status"])

    except Exception as e:
        if use_mutex and concurrency_mutex.locked():
            current_test_status["lock_state"] = "UNLOCKED"
            current_test_status["lock_holder"] = None
            concurrency_mutex.release()
        log_event(thread_idx, thread_name, "EXCEPTION", str(e), "FAILED")
        results_dict[thread_idx]["status"] = "FAILED"
        results_dict[thread_idx]["current_step"] = f"Error: {str(e)}"
    finally:
        conn.close()

def run_controlled_concurrency_test(num_threads: int = 5, initial_copies: int = 1, use_mutex: bool = True, book_id: str = "B100"):
    """
    Prepares test book state, spawns concurrent threads, synchronizes via Barrier,
    collects event traces, and verifies safety invariants.
    Defaults to 5 student threads as per main specification scenario.
    """
    global current_test_events, current_test_status, _global_event_seq

    # Ensure race condition test never corrupts actual library database
    # For Mutex OFF or Demo Book B100, always reset the isolated demo book
    if not use_mutex or book_id == "B100":
        book_id = "B100"  # Isolate race condition runs strictly to benchmark book
        reset_concurrency_test_book(initial_copies=initial_copies)

    with _event_log_lock:
        _global_event_seq = 0
        current_test_events.clear()
        current_test_status.update({
            "is_running": True,
            "lock_state": "UNLOCKED",
            "lock_holder": None,
            "total_threads": num_threads,
            "initial_copies": initial_copies,
            "successful_issues": 0,
            "failed_requests": 0,
            "mutex_enabled": use_mutex,
            "invariants_passed": True,
            "summary_message": "Test initialized...",
            "student_threads": []
        })

    # Prepare students for threads
    students = models.get_all_students()
    thread_students = []
    for i in range(num_threads):
        if i < len(students):
            thread_students.append((students[i]['student_id'], students[i]['name']))
        else:
            s_name = f"Student {i+1}"
            s_email = f"student{i+1}@university.edu"
            existing = models.get_student_by_email(s_email)
            if existing:
                thread_students.append((existing['student_id'], existing['name']))
            else:
                sid = models.create_student(s_name, s_email, "dummyhash")
                thread_students.append((sid, s_name))

    log_event(0, "System Coordinator", "TEST_INITIALIZED",
              f"Initialized concurrency test on '{book_id}' with {initial_copies} available copy(ies) and {num_threads} simultaneous student requests. Mutex: {'ENABLED' if use_mutex else 'DISABLED'}.",
              "RUNNING")

    # Step 1: Student Thread Created
    for idx in range(1, num_threads + 1):
        sid, sname = thread_students[idx - 1]
        log_event(idx, f"Student {idx} ({sname})", "THREAD_CREATED", f"Initialized thread for Student {idx} ({sname})", "WAITING")

    start_barrier = threading.Barrier(num_threads)
    threads = []
    results_dict = {}

    # Step 2: Spawn and Start Threads
    for idx in range(1, num_threads + 1):
        sid, sname = thread_students[idx - 1]
        t = threading.Thread(
            target=_worker_thread_task,
            args=(idx, sid, sname, book_id, use_mutex, start_barrier, results_dict),
            name=f"OS-Student-Thread-{idx}"
        )
        threads.append(t)

    # Start all threads simultaneously
    for t in threads:
        t.start()

    # Wait for all threads to join/finish
    for t in threads:
        t.join()

    # Consolidate results
    results_list = [results_dict[i] for i in sorted(results_dict.keys())]
    successful_count = sum(1 for r in results_list if r['status'] == 'COMPLETED')
    failed_count = sum(1 for r in results_list if r['status'] != 'COMPLETED')

    # Query DB to check copies status & active transactions
    conn = get_db_connection()
    final_copies = conn.execute("""
        SELECT copy_id, status FROM book_copies WHERE book_id = ?
    """, (book_id,)).fetchall()
    
    active_txs = conn.execute("""
        SELECT t.transaction_id, t.copy_id, t.student_id, s.name as student_name
        FROM transactions t
        JOIN book_copies c ON t.copy_id = c.copy_id
        JOIN students s ON t.student_id = s.student_id
        WHERE c.book_id = ? AND t.status = 'ACTIVE'
    """, (book_id,)).fetchall()
    conn.close()

    # Invariant Check:
    # 1. Successful issues must not exceed initial available copies
    # 2. No physical copy should have duplicate active transactions
    copy_tx_counts = {}
    for tx in active_txs:
        copy_tx_counts[tx['copy_id']] = copy_tx_counts.get(tx['copy_id'], 0) + 1

    has_duplicate_issue = any(cnt > 1 for cnt in copy_tx_counts.values())
    exceeded_copies = successful_count > initial_copies

    invariants_passed = (not exceeded_copies) and (not has_duplicate_issue)

    if use_mutex:
        if invariants_passed:
            summary = (
                f"MUTEX SYNCHRONIZATION SUCCESS: Exactly {successful_count} copy was issued out of {initial_copies} available. "
                f"The remaining {failed_count} students received 'Book Unavailable'. Mutual exclusion strictly enforced!"
            )
            log_event(0, "System Coordinator", "TEST_PASSED", summary, "COMPLETED")
        else:
            summary = "MUTEX TEST FAILED: Concurrency violation detected."
            log_event(0, "System Coordinator", "TEST_FAILED", summary, "FAILED")
    else:
        if not invariants_passed or (num_threads > initial_copies and successful_count > initial_copies):
            summary = (
                f"RACE CONDITION OBSERVED! Without Mutex synchronization, {successful_count} students simultaneously issued "
                f"the single copy. Data inconsistency and race condition demonstrated safely on isolated test data!"
            )
            log_event(0, "System Coordinator", "RACE_CONDITION_DEMONSTRATED", summary, "FAILED")
        else:
            summary = f"No race collision occurred on this specific timing run. Try re-running to observe collision."
            log_event(0, "System Coordinator", "RACE_CONDITION_TEST", summary, "WAITING")

    with _event_log_lock:
        current_test_status.update({
            "is_running": False,
            "lock_state": "UNLOCKED",
            "lock_holder": None,
            "successful_issues": successful_count,
            "failed_requests": failed_count,
            "invariants_passed": invariants_passed,
            "summary_message": summary,
            "active_transactions": [dict(t) for t in active_txs],
            "copies_state": [dict(c) for c in final_copies],
            "student_threads": results_list
        })

    return get_concurrency_state()
