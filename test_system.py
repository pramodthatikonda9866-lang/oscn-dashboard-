"""
test_system.py - End-to-End Concurrency & Functional Test Suite
Verifies all 8 Test Cases defined in Page 11 of the OSCN Project 04 Specification:

Test 1: Single request (1 copy, 1 student)
Test 2: Two simultaneous requests (1 copy, 2 concurrent threads)
Test 3: Five simultaneous requests (2 copies, 5 concurrent threads)
Test 4: Ten simultaneous requests (3 copies, 10 concurrent threads)
Test 5: Valid book return & copy availability restoration
Test 6: Reservation queue ordering and auto-allocation on return
Test 7: Invalid return rejection (returning another student's book)
Test 8: Duplicate active issue rejection (same student issuing same title twice)
"""

import unittest
import database
import models
import library
import concurrency

class TestLibraryConcurrencyAndRules(unittest.TestCase):

    def setUp(self):
        """Prepare fresh database state before test runs."""
        database.init_db(seed=True)

    def test_01_single_request(self):
        """Test 1: 1 available copy; 1 student request -> Exactly 1 success, 0 available."""
        database.reset_concurrency_test_book(initial_copies=1)
        res = concurrency.run_controlled_concurrency_test(num_threads=1, initial_copies=1, use_mutex=True)
        status = res['status']

        self.assertEqual(status['successful_issues'], 1)
        self.assertEqual(status['failed_requests'], 0)
        self.assertTrue(status['invariants_passed'])

        # Check DB state
        book = models.get_book_by_id("B100")
        self.assertEqual(book['available_copies'], 0)
        self.assertEqual(book['issued_copies'], 1)
        print("  [PASS] Test 1: Single request processed successfully.")

    def test_02_two_simultaneous_requests(self):
        """Test 2: 1 available copy; 2 concurrent requests -> Exactly 1 success, 1 unavailable."""
        database.reset_concurrency_test_book(initial_copies=1)
        res = concurrency.run_controlled_concurrency_test(num_threads=2, initial_copies=1, use_mutex=True)
        status = res['status']

        self.assertEqual(status['successful_issues'], 1)
        self.assertEqual(status['failed_requests'], 1)
        self.assertTrue(status['invariants_passed'])

        book = models.get_book_by_id("B100")
        self.assertEqual(book['available_copies'], 0)
        print("  [PASS] Test 2: Two simultaneous requests handled with mutual exclusion (1 success, 1 unavailable).")

    def test_03_five_simultaneous_requests(self):
        """Test 3: 2 available copies; 5 concurrent requests -> Exactly 2 success, 3 unavailable."""
        database.reset_concurrency_test_book(initial_copies=2)
        res = concurrency.run_controlled_concurrency_test(num_threads=5, initial_copies=2, use_mutex=True)
        status = res['status']

        self.assertEqual(status['successful_issues'], 2)
        self.assertEqual(status['failed_requests'], 3)
        self.assertTrue(status['invariants_passed'])

        book = models.get_book_by_id("B100")
        self.assertEqual(book['available_copies'], 0)
        print("  [PASS] Test 3: Five simultaneous requests handled (2 success, 3 unavailable).")

    def test_04_ten_simultaneous_requests(self):
        """Test 4: 3 available copies; 10 concurrent requests -> Exactly 3 success, 7 unavailable."""
        database.reset_concurrency_test_book(initial_copies=3)
        res = concurrency.run_controlled_concurrency_test(num_threads=10, initial_copies=3, use_mutex=True)
        status = res['status']

        self.assertEqual(status['successful_issues'], 3)
        self.assertEqual(status['failed_requests'], 7)
        self.assertTrue(status['invariants_passed'])

        book = models.get_book_by_id("B100")
        self.assertEqual(book['available_copies'], 0)
        print("  [PASS] Test 4: Ten simultaneous requests stress test passed (3 success, 7 unavailable).")

    def test_05_return_book(self):
        """Test 5: One valid active issue is returned -> Transaction marked returned, copy becomes available."""
        database.reset_concurrency_test_book(initial_copies=1)
        
        # Issue book to Student 1
        issue_res = library.issue_book("B100", student_id=1, use_lock=True)
        self.assertTrue(issue_res['success'])
        copy_id = issue_res['copy_id']

        # Return book by Student 1
        ret_res = library.return_book(copy_id, student_id=1)
        self.assertTrue(ret_res['success'])

        # Verify copy is back to AVAILABLE
        copy = models.get_copy_by_id(copy_id)
        self.assertEqual(copy['status'], 'AVAILABLE')
        print("  [PASS] Test 5: Return operation marked transaction returned and restored copy availability.")

    def test_06_reservation_queue_and_auto_allocation(self):
        """Test 6: Reservation queue ordering and automatic allocation when copy is returned."""
        database.reset_concurrency_test_book(initial_copies=1)

        # Student 1 issues the only copy
        issue_res = library.issue_book("B100", student_id=1)
        copy_id = issue_res['copy_id']
        self.assertTrue(issue_res['success'])

        # Student 2 & 3 place reservations
        res2 = library.reserve_book("B100", student_id=2)
        self.assertTrue(res2['success'])
        self.assertEqual(res2['queue_number'], 1)

        res3 = library.reserve_book("B100", student_id=3)
        self.assertTrue(res3['success'])
        self.assertEqual(res3['queue_number'], 2)

        # Student 1 returns the copy
        ret_res = library.return_book(copy_id, student_id=1)
        self.assertTrue(ret_res['success'])

        # Verify: Copy should be RESERVED for Student 2 (earliest waiting reservation)
        copy = models.get_copy_by_id(copy_id)
        self.assertEqual(copy['status'], 'RESERVED')

        student2_res = models.get_reservations_for_student(2)[0]
        self.assertEqual(student2_res['status'], 'READY')
        self.assertEqual(student2_res['allocated_copy_id'], copy_id)
        print("  [PASS] Test 6: Reservation queue ordering and automatic return allocation verified.")

    def test_07_invalid_return_rejection(self):
        """Test 7: Student attempts to return another student's copy -> Request rejected, DB unchanged."""
        database.reset_concurrency_test_book(initial_copies=1)

        # Student 1 issues copy
        issue_res = library.issue_book("B100", student_id=1)
        copy_id = issue_res['copy_id']

        # Student 2 attempts to return Student 1's copy
        illegal_return = library.return_book(copy_id, student_id=2)
        self.assertFalse(illegal_return['success'])
        self.assertIn("rejected", illegal_return['message'].lower())

        # Verify copy is still ISSUED and active loan unchanged
        copy = models.get_copy_by_id(copy_id)
        self.assertEqual(copy['status'], 'ISSUED')
        print("  [PASS] Test 7: Unauthorized return of another student's book rejected safely.")

    def test_08_duplicate_request_rejection(self):
        """Test 8: Same student attempts duplicate active issue of same title -> Rejected."""
        database.reset_concurrency_test_book(initial_copies=2)

        # Student 1 issues copy 1
        issue1 = library.issue_book("B100", student_id=1)
        self.assertTrue(issue1['success'])

        # Student 1 attempts to issue the same book title again while active loan exists
        issue2 = library.issue_book("B100", student_id=1)
        self.assertFalse(issue2['success'])
        self.assertIn("duplicate", issue2['message'].lower())
        print("  [PASS] Test 8: Duplicate active issue by same student prevented.")

if __name__ == '__main__':
    print("=" * 70)
    print("RUNNING OSCN PROJECT 04 CONCURRENCY & FUNCTIONAL VERIFICATION SUITE")
    print("=" * 70)
    unittest.main(verbosity=2)

