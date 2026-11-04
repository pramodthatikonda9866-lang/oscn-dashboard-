# 📚 Library Book Issue & Reservation System
### Operating Systems & Concurrency (OSCN) — Project 04
**Core Stack:** Python 3 • Flask • SQLite • `threading.Lock()` • HTML5/CSS3/Vanilla JS

---

## 🌟 Overview
The **Library Book Issue and Reservation System** is a full-featured web application designed to demonstrate fundamental **Operating Systems (OS)** concurrency concepts in action.

Its core academic objective is solving the **Shared Resource Contention Problem**: when two or more students simultaneously request the last remaining copy of a book, unsynchronized execution results in a **Race Condition** (over-issuing the same physical copy). By implementing a mutual exclusion lock (`threading.Lock()`), the critical section (checking copy availability, reserving copy, and recording active loan transaction) is protected, ensuring strict mutual exclusion and atomicity.

---

## 🚀 Key Features

1. **Student Web Portal**:
   - Student registration and secure login (hashed passwords with Werkzeug).
   - Live book catalog with real-time copy availability counts and search filters.
   - Mutex-synchronized book issuing.
   - Safe returns with ownership validation.
   - FIFO reservation queue for unavailable books with automatic copy allocation upon return.
   - Personal active loans and transaction history view.

2. **Admin / Librarian Portal**:
   - Separate admin authentication (`admin` / `admin123`).
   - Book catalog and copy-level management (add book, add extra physical copy, delete book).
   - Enrolled student directory.
   - Global active loan transactions audit.
   - Global reservation queues inspection.

3. **⚡ Dedicated OS Concurrency Monitor**:
   - **Real Python Threads**: Spawns actual `threading.Thread` instances synchronized with `threading.Barrier`.
   - **Live Mutex Lock Visualizer**: Visual indicator switching between `LOCKED` (pulsating red) and `UNLOCKED` (steady green).
   - **Chronological Terminal Event Stream**: Displays real-time sequence (`REQUESTED` → `WAITING_FOR_LOCK` → `LOCK_ACQUIRED` → `ENTERED_CRITICAL_SECTION` → `ISSUE_DECISION` → `LOCK_RELEASED`).
   - **Interactive Mutex Toggle**: Compare thread-safe execution (Mutex ON) directly against race conditions (Mutex OFF).
   - **Test Matrix Presets**: 1-click execution for all 4 concurrency scenarios specified in Page 11.
   - **Safety Invariant Verification**: Validates that successful issues never exceed initial available copies and no physical copy is double-issued.

---

## 📁 Project File Structure

```
OSCN(PRODUCT-2)/
├── app.py                  # Flask web server, route registry & session handling
├── database.py             # SQLite connection factory, schema & foreign key management
├── models.py               # Data access layer for students, books, copies & transactions
├── auth.py                 # Password hashing, login validation & route guards
├── library.py              # Business operations (issue, return, reserve, auto-allocation)
├── concurrency.py          # Mutex lock, thread spawning, barrier sync & event logging
├── test_system.py          # Complete 8-part automated verification test suite
├── requirements.txt        # Python dependency manifest (Flask, Werkzeug)
├── FACULTY_EVALUATION.md   # Complete viva voce Q&A guide & demonstration script
├── README.md               # Documentation and setup instructions
├── library.db              # SQLite relational database (created at runtime)
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Base layout with navbar, alerts & footer
│   ├── login.html          # Authentication page with demo quick-fill
│   ├── register.html       # Student registration page
│   ├── dashboard.html      # Student dashboard & active loan summary
│   ├── books.html          # Book catalogue & live search
│   ├── my_books.html       # Borrowed books & transaction history
│   ├── reservations.html   # Ordered reservation queues
│   ├── admin.html          # Librarian portal & inventory management
│   └── concurrency.html    # Interactive OS Concurrency Monitor
└── static/
    ├── css/style.css       # Clean, modern palette (Navy, Royal Blue, Teal)
    ├── js/script.js        # Dynamic search, modals & live concurrency runner
    └── images/             # Static assets directory
```

---

## ⚡ Quick Start & Installation

### 1. Requirements
- Python 3.9+ (Python 3.14 compatible)
- pip

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Database & Seed Sample Data
```bash
python database.py
```

### 4. Run Flask Server
```bash
python app.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔑 Default Credentials

| Role | Username / Email | Password |
| :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` |
| **Librarian** | `librarian` | `librarian123` |
| **Demo Student 1** | `john@university.edu` | `student123` |
| **Demo Student 2** | `alice@university.edu` | `student123` |
| **Demo Student 3** | `bob@university.edu` | `student123` |

*(Quick-fill buttons are also provided directly on the login page for instant sign-in).*

---

## 🧪 Running the Verification Test Suite

To verify all 8 test cases from Page 11 of the OSCN Specification:

```bash
python test_system.py
```

### Expected Output:
```
======================================================================
RUNNING OSCN PROJECT 04 CONCURRENCY & FUNCTIONAL VERIFICATION SUITE
======================================================================
  [PASS] Test 1: Single request processed successfully.
  [PASS] Test 2: Two simultaneous requests handled with mutual exclusion (1 success, 1 unavailable).
  [PASS] Test 3: Five simultaneous requests handled (2 success, 3 unavailable).
  [PASS] Test 4: Ten simultaneous requests stress test passed (3 success, 7 unavailable).
  [PASS] Test 5: Return operation marked transaction returned and restored copy availability.
  [PASS] Test 6: Reservation queue ordering and automatic return allocation verified.
  [PASS] Test 7: Unauthorized return of another student's book rejected safely.
  [PASS] Test 8: Duplicate active issue by same student prevented.

----------------------------------------------------------------------
Ran 8 tests in 0.769s

OK
```

---

## 🔬 How Mutex Synchronization Works

```python
import threading

# Shared Mutex Lock Primitive
book_lock = threading.Lock()

def issue_book(book_id, student_id):
    # Acquire lock: only 1 thread enters at a time; others block and wait
    with book_lock:
        # ================= CRITICAL SECTION START =================
        # 1. Query SQLite: Check if physical copy is AVAILABLE
        # 2. Select available copy (e.g. B100-C001)
        # 3. Update copy status to 'ISSUED'
        # 4. Insert active loan transaction with 14-day due date
        # 5. Commit SQLite transaction
        # ================== CRITICAL SECTION END ==================
        pass
    # Lock is automatically released here for the next waiting thread
```

When Mutex is disabled, competing threads both read the same copy as `AVAILABLE`, leading to duplicate loans of the same physical copy. When Mutex is enabled, mutual exclusion is strictly enforced.

---

## 📖 Faculty Evaluation Guide
Refer to **`FACULTY_EVALUATION.md`** for answers to all 13 standard viva questions and the step-by-step demonstration walkthrough sequence.
