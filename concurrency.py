"""
concurrency.py - Multithreading, Mutex Synchronization & Concurrency Monitor
Implements real Python thread spawning, threading.Lock() mutual exclusion,
barrier synchronization, event sequence logging, and controlled test execution.
"""

import threading
import time
from datetime import datetime
from database import get_db_connection, reset_concurrency_test_book
import models

# Dedicated Mutex for the Library Concurrency Test
concurrency_mutex = threading.Lock()

# Thread-safe event logging structures
_event_log_lock = threading.Lock()
_global_event_seq = 0
current_test_events = []
current_test_status = {
    "is_running": False,
    "lock_state": "UNLOCKED",
    "lock_holder": None,
    "total_threads": 0,
    "initial_copies": 0,
    "successful_issues": 0,
    "failed_requests": 0,
    "mutex_enabled": True,
    "invariants_passed": True,
    "summary_message": "Ready to run concurrency test."
}

def log_event(thread_id: int, thread_name: str, event_type: str, details: str = "", status_badge: str = "INFO"):
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
    results: list
):
    """
    Worker thread representing an individual student's concurrent request.
    Follows the exact event sequence required by Section 9 & 11:
    REQUESTED -> WAITING_FOR_LOCK -> LOCK_ACQUIRED -> ENTERED_CRITICAL_SECTION
    -> ISSUE_DECISION -> LOCK_RELEASED
    """
    thread_name = f"Thread-{thread_idx} ({student_name})"

    # Synchronize all threads to release at the exact same instant
    start_barrier.wait()

    # Step 1: REQUESTED
    log_event(thread_idx, thread_name, "REQUESTED", f"Student requested to issue book '{book_id}'", "WAITING")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if use_mutex:
            # Step 2: WAITING_FOR_LOCK
            log_event(thread_idx, thread_name, "WAITING_FOR_LOCK", "Thread waiting to acquire mutex lock...", "WAITING")
            
            # Acquire Mutex
            concurrency_mutex.acquire()
            current_test_status["lock_state"] = "LOCKED"
            current_test_status["lock_holder"] = thread_name

            # Step 3 & 4: LOCK_ACQUIRED & ENTERED_CRITICAL_SECTION
            log_event(thread_idx, thread_name, "LOCK_ACQUIRED", "Mutex lock acquired successfully.", "LOCKED")
            log_event(thread_idx, thread_name, "ENTERED_CRITICAL_SECTION", "Entered critical section: checking available copies in SQLite", "CRITICAL")

            # CRITICAL SECTION LOGIC
            # 1. Query available copy
            available_copy = cursor.execute("""
                SELECT copy_id FROM book_copies 
                WHERE book_id = ? AND status = 'AVAILABLE' 
                ORDER BY copy_id ASC LIMIT 1
            """, (book_id,)).fetchone()

            # Small processing simulation inside critical section
            time.sleep(0.02)

            if available_copy:
                copy_id = available_copy['copy_id']
                # 2. Update status
                cursor.execute("UPDATE book_copies SET status = 'ISSUED' WHERE copy_id = ?", (copy_id,))
                
                # 3. Insert transaction
                due_date = (datetime.now() + time.timezone_at_load() if hasattr(time, 'timezone_at_load') else datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO transactions (student_id, copy_id, due_date, status)
                    VALUES (?, ?, ?, 'ACTIVE')
                """, (student_id, copy_id, due_date))
                conn.commit()

                log_event(thread_idx, thread_name, "ISSUE_SUCCESS", f"Assigned Copy {copy_id}. Transaction committed.", "ISSUED")
                results.append({"thread": thread_idx, "student": student_name, "status": "SUCCESS", "copy": copy_id})
            else:
                log_event(thread_idx, thread_name, "NO_COPY_AVAILABLE", "All copies exhausted. Request rejected safely.", "UNAVAILABLE")
                results.append({"thread": thread_idx, "student": student_name, "status": "FAILED", "reason": "No copy available"})

            # Step 5: LOCK_RELEASED
            current_test_status["lock_state"] = "UNLOCKED"
            current_test_status["lock_holder"] = None
            concurrency_mutex.release()
            log_event(thread_idx, thread_name, "LOCK_RELEASED", "Released mutex lock. Critical section exited.", "UNLOCKED")

        else:
            # UNSAFE EXECUTION PATH (NO MUTEX - DEMONSTRATES RACE CONDITION)
            log_event(thread_idx, thread_name, "NO_LOCK_USED", "WARNING: Mutex lock disabled! Entering unprotected critical section.", "DANGER")
            
            # Both threads read availability at the same time
            available_copy = cursor.execute("""
                SELECT copy_id FROM book_copies 
                WHERE book_id = ? AND status = 'AVAILABLE' 
                ORDER BY copy_id ASC LIMIT 1
            """, (book_id,)).fetchone()

            # Latency gap allows second thread to observe the same copy as AVAILABLE!
            time.sleep(0.06)

            if available_copy:
                copy_id = available_copy['copy_id']
                cursor.execute("UPDATE book_copies SET status = 'ISSUED' WHERE copy_id = ?", (copy_id,))
                cursor.execute("""
                    INSERT INTO transactions (student_id, copy_id, due_date, status)
                    VALUES (?, ?, datetime('now', '+14 days'), 'ACTIVE')
                """, (student_id, copy_id))
                conn.commit()

                log_event(thread_idx, thread_name, "ISSUE_SUCCESS (RACE CONDITION)", f"Unsafely assigned copy {copy_id}!", "ISSUED")
                results.append({"thread": thread_idx, "student": student_name, "status": "SUCCESS", "copy": copy_id})
            else:
                log_event(thread_idx, thread_name, "NO_COPY_AVAILABLE", "Observed 0 available copies.", "UNAVAILABLE")
                results.append({"thread": thread_idx, "student": student_name, "status": "FAILED", "reason": "No copy available"})

    except Exception as e:
        if use_mutex and concurrency_mutex.locked():
            current_test_status["lock_state"] = "UNLOCKED"
            current_test_status["lock_holder"] = None
            concurrency_mutex.release()
        log_event(thread_idx, thread_name, "EXCEPTION", str(e), "ERROR")
        results.append({"thread": thread_idx, "student": student_name, "status": "ERROR", "reason": str(e)})
    finally:
        conn.close()

def run_controlled_concurrency_test(num_threads: int = 2, initial_copies: int = 1, use_mutex: bool = True, book_id: str = "B100"):
    """
    Prepares test book state, spawns concurrent threads, synchronizes via Barrier,
    collects event traces, and verifies safety invariants.
    """
    global current_test_events, current_test_status, _global_event_seq

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
            "summary_message": "Test initialized..."
        })

    # Step 0: Reset test book state
    reset_concurrency_test_book(initial_copies=initial_copies)

    # Fetch real or synthetic students
    students = models.get_all_students()
    thread_students = []
    for i in range(num_threads):
        if i < len(students):
            thread_students.append((students[i]['student_id'], students[i]['name']))
        else:
            # Synthetic student for tests with > 5 threads
            s_name = f"Test Student {i+1}"
            s_email = f"teststudent{i+1}@oscn.test"
            existing = models.get_student_by_email(s_email)
            if existing:
                thread_students.append((existing['student_id'], existing['name']))
            else:
                sid = models.create_student(s_name, s_email, "dummyhash")
                thread_students.append((sid, s_name))

    log_event(0, "System Coordinator", "TEST_INITIALIZED",
              f"Setting up test on '{book_id}' with {initial_copies} available copy(ies) and {num_threads} concurrent threads. Mutex: {'ENABLED' if use_mutex else 'DISABLED'}.",
              "INFO")

    start_barrier = threading.Barrier(num_threads)
    threads = []
    results = []

    # Spawn threads
    for idx in range(1, num_threads + 1):
        sid, sname = thread_students[idx - 1]
        t = threading.Thread(
            target=_worker_thread_task,
            args=(idx, sid, sname, book_id, use_mutex, start_barrier, results),
            name=f"OS-Thread-{idx}"
        )
        threads.append(t)

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Evaluate results & invariants (Pass criteria from Page 11)
    successful_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    failed_count = sum(1 for r in results if r['status'] != 'SUCCESS')

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
    # 2. No copy should have duplicate active transactions
    copy_tx_counts = {}
    for tx in active_txs:
        copy_tx_counts[tx['copy_id']] = copy_tx_counts.get(tx['copy_id'], 0) + 1

    has_duplicate_issue = any(cnt > 1 for cnt in copy_tx_counts.values())
    exceeded_copies = successful_count > initial_copies

    invariants_passed = (not exceeded_copies) and (not has_duplicate_issue)

    if use_mutex:
        if invariants_passed:
            summary = (
                f"MUTEX VERIFICATION PASSED: Exactly {successful_count} copy(ies) issued out of {initial_copies} available. "
                f"{failed_count} threads cleanly rejected with NO_COPY_AVAILABLE. Mutual exclusion preserved!"
            )
            log_event(0, "System Coordinator", "TEST_PASSED", summary, "SUCCESS")
        else:
            summary = "MUTEX TEST FAILED: Concurrency violation detected."
            log_event(0, "System Coordinator", "TEST_FAILED", summary, "ERROR")
    else:
        if not invariants_passed or (num_threads > initial_copies and successful_count > initial_copies):
            summary = (
                f"RACE CONDITION OBSERVED! Without mutex synchronization, {successful_count} threads simultaneously issued "
                f"only {initial_copies} physical copy(ies). Data inconsistency detected as expected!"
            )
            log_event(0, "System Coordinator", "RACE_CONDITION_DEMONSTRATED", summary, "DANGER")
        else:
            summary = f"No race collision occurred on this specific timing run. Try re-running or increasing threads."
            log_event(0, "System Coordinator", "RACE_CONDITION_TEST", summary, "WARNING")

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
            "copies_state": [dict(c) for c in final_copies]
        })

    return get_concurrency_state()
