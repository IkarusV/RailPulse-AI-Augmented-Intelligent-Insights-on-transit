import unittest

from database import DatabaseError, execute_readonly


class DatabaseTests(unittest.TestCase):
    def test_snapshot_row_count(self):
        columns, rows = execute_readonly("SELECT COUNT(*) AS departures FROM departures")
        self.assertEqual(columns, ["departures"])
        self.assertEqual(rows, [[211]])

    def test_database_rejects_write_even_without_guard(self):
        with self.assertRaises(DatabaseError):
            execute_readonly("DELETE FROM departures")


if __name__ == "__main__":
    unittest.main()
