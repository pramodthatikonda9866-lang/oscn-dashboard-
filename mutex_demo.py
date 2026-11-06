import threading
import time

available_copies = 3

# Create Mutex Lock
mutex = threading.Lock()


def issue_book(student_id, use_mutex):
    global available_copies

    if use_mutex:

        # Mutex ON
        with mutex:

            if available_copies > 0:
                available_copies -= 1
                print(f"Student {student_id}: BOOK ISSUED")

            else:
                print(f"Student {student_id}: NO_COPY_AVAILABLE")

    else:

        # Mutex OFF - Race Condition
        if available_copies > 0:

            time.sleep(0.1)
            available_copies -= 1

            print(f"Student {student_id}: BOOK ISSUED")

        else:
            print(f"Student {student_id}: NO_COPY_AVAILABLE")


# Create and execute threads
students = []

for i in range(10):
    t = threading.Thread(
        target=issue_book,
        args=(i + 1, True)
    )
    students.append(t)

# Start threads
for t in students:
    t.start()

# Wait for completion
for t in students:
    t.join()

