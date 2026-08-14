import unittest

from sql_guard import UnsafeQuery, validate_sql


class SQLGuardTests(unittest.TestCase):
    def assert_blocked(self, sql):
        with self.assertRaises(UnsafeQuery):
            validate_sql(sql)

    def test_accepts_grouped_select(self):
        sql = validate_sql(
            "SELECT platform, ROUND(AVG(delay_minutes), 2) AS avg_delay "
            "FROM departures GROUP BY platform ORDER BY avg_delay DESC LIMIT 6;"
        )
        self.assertIn("FROM departures", sql)

    def test_adds_default_limit(self):
        sql = validate_sql("SELECT COUNT(*) AS departures FROM departures;")
        self.assertTrue(sql.endswith("LIMIT 100"))

    def test_blocks_mutations(self):
        for operation in ("DELETE", "UPDATE", "DROP", "INSERT", "ALTER"):
            with self.subTest(operation=operation):
                self.assert_blocked(f"{operation} FROM departures")

    def test_blocks_stacked_statements(self):
        self.assert_blocked("SELECT COUNT(*) FROM departures; DROP TABLE departures;")

    def test_blocks_comments(self):
        self.assert_blocked("SELECT COUNT(*) FROM departures -- ignore safety")

    def test_blocks_select_star(self):
        self.assert_blocked("SELECT * FROM departures LIMIT 10")

    def test_blocks_unknown_table(self):
        self.assert_blocked("SELECT password FROM users LIMIT 10")

    def test_blocks_joins_and_unions(self):
        self.assert_blocked(
            "SELECT a.vehicle_id FROM departures a JOIN departures b "
            "ON a.vehicle_id = b.vehicle_id LIMIT 10"
        )
        self.assert_blocked(
            "SELECT vehicle_id FROM departures UNION SELECT vehicle_id FROM departures"
        )

    def test_blocks_excessive_limit(self):
        self.assert_blocked("SELECT vehicle_id FROM departures LIMIT 101")


if __name__ == "__main__":
    unittest.main()
