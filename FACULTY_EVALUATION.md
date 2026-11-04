# 🎓 Faculty Evaluation & Viva Voce Guide
## OSCN Project 04: Library Book Issue & Reservation System Using Python Mutex Synchronization

---

## 📌 Executive Summary
This project provides a software demonstration of **Operating Systems & Concurrency (OSCN)** principles. It manages real library operations (cataloging, multi-copy availability tracking, borrowing, returning, FIFO reservation queuing) while serving as an empirical platform for observing **Race Conditions**, **Mutex Synchronization**, **Critical Section Protection**, and **ACID Transactions**.

---

## 🔍 Core OS Concepts & Code Mapping

| OS Concept | Conceptual Meaning | Where & How It Is Implemented in Code |
| :--- | :--- | :--- |
| **Process** | An executing program with isolated memory space. | The running Flask application instance (`app.py`). |
| **Thread** | A lightweight execution path sharing process address space. | `threading.Thread(target=_worker_thread_task, ...)` in `concurrency.py`. |
| **Shared Resource** | Memory/database state accessed by concurrent threads. | Physical book copy availability (`book_copies.status`) and active issue records (`transactions`). |
| **Race Condition** | Flawed outcome when concurrent unsynchronized threads read/modify shared state simultaneously. | When Mutex is OFF in `concurrency.py`, two threads both read `status = 'AVAILABLE'` for the single remaining copy, producing duplicate active loans. |
| **Mutex Lock** | Mutual-exclusion lock ensuring at most one thread executes a critical section at a time. | `concurrency_mutex = threading.Lock()` in `concurrency.py` and `library_lock = threading.Lock()` in `library.py`. |
| **Critical Section** | Code block accessing shared resources that must execute under mutual exclusion. | The code block checking copy availability, marking copy `ISSUED`, and writing transaction records. |
| **Atomicity** | All-or-nothing execution of critical state updates. | Enclosed within `with book_lock:` plus SQLite transaction `conn.commit()` / `conn.rollback()`. |
| **Deadlock Avoidance** | Preventing threads from waiting indefinitely for held resources. | Single unified lock hierarchy; context-manager auto-release (`with book_lock:`); zero nested locks. |

---

## ❓ 13 Standard Faculty Viva Questions & Answers

### 1. Why do we import Python's `threading` module?
> **Answer:** `threading` provides OS-level thread primitives in Python. We use `threading.Thread` to simulate multiple students requesting the last available book copy concurrently at the exact same millisecond, and `threading.Lock` to synchronize their access.

### 2. What does `threading.Lock()` do?
> **Answer:** It creates a mutual exclusion (mutex) lock object. It has two fundamental states: **unlocked** and **locked**. When one thread acquires it, any other thread attempting to acquire it is blocked (put into the OS wait queue) until the holding thread releases it.

### 3. What does `acquire()` do?
> **Answer:** `acquire()` attempts to obtain the lock. If the lock is currently unlocked, the calling thread changes it to locked and proceeds immediately. If the lock is already held by another thread, the calling thread suspends execution until the lock is released.

### 4. What does `release()` do?
> **Answer:** `release()` changes the lock state from locked to unlocked, allowing one waiting thread in the queue to awaken, acquire the lock, and enter the critical section.

### 5. Why is the context manager `with book_lock:` preferred over manual `acquire()` / `release()`?
> **Answer:** `with book_lock:` guarantees that `release()` is invoked automatically when leaving the block, even if an unexpected exception, error, or early `return` occurs. This prevents the lock from being permanently held, which would cause **deadlock** or system freezing.

### 6. What is a Critical Section in this project?
> **Answer:** In `library.py` and `concurrency.py`, the critical section is the sequential logic where:
> 1. The database is checked for an `AVAILABLE` copy of the requested book.
> 2. The copy status is updated to `ISSUED`.
> 3. An active loan record is inserted into the `transactions` table.
> If these steps are not mutually exclusive, a race condition occurs.

### 7. What is a Race Condition in the context of library book issuing?
> **Answer:** If two students submit requests for the sole remaining copy of a book at the same time:
> - Thread A checks the database: Copy 1 is AVAILABLE.
> - Before Thread A writes ISSUED, Thread B checks the database: Copy 1 is still observed as AVAILABLE.
> - Both threads proceed to issue Copy 1.
> Both students receive a success confirmation, but only one physical copy exists in the library. This is a classic **Time-of-Check to Time-of-Use (TOCTOU)** race condition.

### 8. What is a Thread?
> **Answer:** A thread is the smallest schedulable unit of CPU execution within a process. Multiple threads share the same heap memory, database connection descriptors, and global variables, allowing fast communication but requiring careful synchronization.

### 9. What do `start()` and `join()` do?
> **Answer:**
> - `start()`: Spawns the thread and tells the OS scheduler to begin executing its `run()` or target function.
> - `join()`: Halts the calling thread (the coordinator) until the target thread has completed its execution. This ensures all simulated requests finish before summarizing results.

### 10. What happens if the mutex is disabled?
> **Answer:** When the mutex is disabled, we remove mutual exclusion. With concurrent threads running and a tiny latency window (e.g., simulating disk I/O), multiple threads interleave their read and write operations. In our Concurrency Monitor, turning Mutex OFF demonstrates multiple students successfully claiming the exact same physical copy (over-allocation / invariant failure).

### 11. What is Deadlock and how does this application prevent it?
> **Answer:** Deadlock is a permanent stall where two or more threads cannot proceed because each is waiting for a resource held by the other (e.g., Thread 1 holds Lock A waiting for Lock B, while Thread 2 holds Lock B waiting for Lock A). We prevent deadlocks by:
> - Using a single mutex lock (`library_lock` / `concurrency_mutex`) rather than multiple nested locks.
> - Always using `with lock:` context managers to guarantee lock release.
> - Designing operations to be non-blocking with clear timeouts.

### 12. Why use SQLite with `sqlite3`?
> **Answer:** SQLite is lightweight, serverless, self-contained, and file-based. It integrates directly with Python without needing external daemon setup (like PostgreSQL or MySQL), making it optimal for local demonstrations while supporting full SQL syntax, foreign key constraints (`PRAGMA foreign_keys = ON`), and ACID guarantees.

### 13. Why do we need both a Python Mutex AND SQLite Database Transactions?
> **Answer:**
> - The **Python Mutex (`threading.Lock`)** coordinates concurrent in-memory execution paths and prevents thread interleaving within the Flask process.
> - The **SQLite Transaction (`BEGIN`, `COMMIT`, `ROLLBACK`)** ensures ACID guarantees on disk persistence: if a database write fails midway, the entire change is rolled back atomically so partial records are never left behind.
> - Together, they form defense-in-depth: Python synchronization controls runtime flow; database constraints enforce data integrity.

---

## 🎬 Recommended 8-Step Live Demonstration Walkthrough

When presenting to faculty, follow this structured script:

1. **Start the System**:
   ```bash
   python app.py
   ```
   Open your browser at `http://127.0.0.1:5000`.

2. **Show Student Portal & Catalogue**:
   - Log in using demo student credentials (`john@university.edu` / `student123`).
   - Browse the Catalogue (`/books`). Point out book `B100` ("Operating System Concepts (Demo Book)"), showing total copies: 1, available: 1.

3. **Navigate to the OS Concurrency Monitor**:
   - Click the top navigation pill: **"⚡ OS Concurrency Monitor"**.
   - Show the live **Mutex Lock State box** (`UNLOCKED`).
   - Show the **Test Scenario Presets** (matching Page 11 of the specification).

4. **Demonstrate Race Condition (Mutex Disabled)**:
   - Select **Test 2: Two Simultaneous Requests (2 Threads, 1 Copy)**.
   - Switch the toggle: **Disable Mutex Lock**.
   - Click **Run Concurrency Test**.
   - **Show the outcome**: Both threads enter simultaneously, both observe the single copy as available, and both issue the same copy! Point out the badge: `RACE CONDITION TRIGGERED`.

5. **Demonstrate Mutex Synchronization (Mutex Enabled)**:
   - Turn the toggle back **ON**: **Enable Python Mutex Lock**.
   - Click **Run Concurrency Test**.
   - **Show the outcome**:
     - `Thread-1` acquires the lock (`LOCKED`).
     - `Thread-2` enters `WAITING_FOR_LOCK` state.
     - `Thread-1` enters the critical section, successfully claims the copy (`ISSUE_SUCCESS`), and releases the lock (`LOCK_RELEASED`).
     - `Thread-2` acquires the released lock, enters the critical section, checks availability, finds 0 copies left, and safely receives `NO_COPY_AVAILABLE`.
     - Invariants status turns green: `PASSED (NO RACE CONDITION)`.

6. **Demonstrate Stress Test (10 Threads / 3 Copies)**:
   - Click **Test 4 Preset** (10 Threads, 3 Copies, Mutex ON).
   - Click **Run Concurrency Test**.
   - Point out that **exactly 3 issues succeed** and **7 threads are cleanly rejected**. Invariants never fail.

7. **Show Return & Reservation Queue Auto-Allocation**:
   - Navigate to a book with 0 copies (e.g. `B104` or `B100`).
   - Place a reservation as Student 2 (receives Queue #1).
   - Place another reservation as Student 3 (receives Queue #2).
   - Return the active loan as Student 1.
   - Show that the system immediately and automatically allocates the returned copy to Student 2 with status `READY` and a 48-hour pickup window!

8. **Run Automated Test Suite**:
   ```bash
   python test_system.py
   ```
   Show faculty all 8 automated unit/concurrency tests passing with 100% green checkmarks.

