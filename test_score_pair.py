"""Comprehensive test suite for score_pair entity resolution."""

import unittest
from score_pair import FieldComparison, MatchResult, PLAN, score_pair


class TestScorePair(unittest.TestCase):
    def setUp(self):
        self.sample_plan = PLAN

    def test_identical_records(self):
        """Identical records should have confidence 1.0 and match all fields."""
        record_a = {
            "name": "Fatima Patel",
            "email": "fatima.patel@example.com",
            "phone": "+91 92792 45222",
            "date_of_birth": "1998-10-13",
            "pin_code": "400020",
            "city": "Mumbai",
        }
        record_b = dict(record_a)
        result = score_pair(record_a, record_b, self.sample_plan)

        self.assertIsInstance(result, MatchResult)
        self.assertAlmostEqual(result.confidence, 1.0, places=4)
        self.assertEqual(len(result.field_scores), 6)
        for score in result.field_scores.values():
            self.assertEqual(score, 1.0)
        self.assertEqual(
            result.algorithm,
            "phonetic+edit_distance+normalized_phone+date+exact+exact",
        )

    def test_phone_formatting_variations(self):
        """Phone numbers with +91, leading 0, spaces, and hyphens should normalize to 1.0."""
        record_a = {"phone": "+91 92792 45222"}
        record_b = {"phone": "092792-45222"}
        plan = [FieldComparison("phone", "normalized_phone", 1.0)]

        result = score_pair(record_a, record_b, plan)
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(result.field_scores["phone"], 1.0)
        self.assertEqual(result.algorithm, "normalized_phone")

    def test_phone_mismatch(self):
        """Different normalized phone numbers should score 0.0."""
        record_a = {"phone": "+91 92792 45222"}
        record_b = {"phone": "92792 45223"}
        plan = [FieldComparison("phone", "normalized_phone", 1.0)]

        result = score_pair(record_a, record_b, plan)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.field_scores["phone"], 0.0)

    def test_date_formatting_and_two_digit_years(self):
        """Different date formats representing the same date should score 1.0, including 2-digit years."""
        # YYYY-MM-DD vs DD.MM.YY (09.12.68 should map to 1968, matching 1968-12-09)
        record_a = {"date_of_birth": "1968-12-09"}
        record_b = {"date_of_birth": "09.12.68"}
        plan = [FieldComparison("date_of_birth", "date", 1.0)]

        result = score_pair(record_a, record_b, plan)
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(result.field_scores["date_of_birth"], 1.0)

        # DD/MM/YYYY vs DD-Mon-YYYY
        record_c = {"date_of_birth": "19/01/1965"}
        record_d = {"date_of_birth": "19-Jan-1965"}
        result2 = score_pair(record_c, record_d, plan)
        self.assertEqual(result2.confidence, 1.0)

        # 2-digit year 2000 (03.11.00 should map to 2000-11-03)
        record_g = {"date_of_birth": "2000-11-03"}
        record_h = {"date_of_birth": "03.11.00"}
        result4 = score_pair(record_g, record_h, plan)
        self.assertEqual(result4.confidence, 1.0)

        # Explicit 4-digit year should not be altered by 2-digit logic
        record_i = {"date_of_birth": "2025-06-15"}
        record_j = {"date_of_birth": "2025-06-15"}
        result5 = score_pair(record_i, record_j, plan)
        self.assertEqual(result5.confidence, 1.0)

        # Different dates
        record_e = {"date_of_birth": "1968-12-09"}
        record_f = {"date_of_birth": "1968-12-10"}
        result3 = score_pair(record_e, record_f, plan)
        self.assertEqual(result3.confidence, 0.0)

    def test_exact_comparison_case_and_whitespace(self):
        """Exact matching should trim whitespace and ignore case."""
        record_a = {"city": " Mumbai  ", "pin_code": "400020"}
        record_b = {"city": "mumbai", "pin_code": " 400020 "}
        plan = [
            FieldComparison("city", "exact", 0.5),
            FieldComparison("pin_code", "exact", 0.5),
        ]

        result = score_pair(record_a, record_b, plan)
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(result.field_scores["city"], 1.0)
        self.assertEqual(result.field_scores["pin_code"], 1.0)

    def test_email_case_and_edit_distance(self):
        """Emails with different case or minor typo should score well via edit distance."""
        # Case variation
        record_a = {"email": "Fatima.Patel@example.com"}
        record_b = {"email": "fatima.patel@example.com"}
        plan = [FieldComparison("email", "edit_distance", 1.0)]
        result = score_pair(record_a, record_b, plan)
        self.assertEqual(result.confidence, 1.0)

        # Minor single typo (1 edit in 24 chars)
        record_c = {"email": "fatima.patel@example.com"}
        record_d = {"email": "fatima.patel@exampel.com"}
        result2 = score_pair(record_c, record_d, plan)
        self.assertGreater(result2.confidence, 0.90)

    def test_name_reordering_initials_and_phonetics(self):
        """Names with reordering, initials, and spelling variations should score well."""
        plan = [FieldComparison("name", "phonetic", 1.0)]

        # Reordering: "Patel, Fatima" vs "Fatima Patel"
        res_reorder = score_pair({"name": "Patel, Fatima"}, {"name": "Fatima Patel"}, plan)
        self.assertEqual(res_reorder.confidence, 1.0)

        # Initial: "S. Bhat" vs "Swathi Bhat"
        res_initial = score_pair({"name": "S. Bhat"}, {"name": "Swathi Bhat"}, plan)
        self.assertGreaterEqual(res_initial.confidence, 0.90)

        # Reordered Initial: "Bhat Swati" vs "S. Bhat"
        res_reorder_init = score_pair({"name": "Bhat Swati"}, {"name": "S. Bhat"}, plan)
        self.assertGreaterEqual(res_reorder_init.confidence, 0.90)

        # Phonetic variation: "Gurprit Khan" vs "GURPREET KHAN"
        res_phonetic = score_pair({"name": "Gurprit Khan"}, {"name": "GURPREET KHAN"}, plan)
        self.assertGreater(res_phonetic.confidence, 0.95)

        # Phonetic variation: "Pooja Iyer" vs "Iyer Puja"
        res_pooja = score_pair({"name": "Pooja Iyer"}, {"name": "Iyer Puja"}, plan)
        self.assertGreater(res_pooja.confidence, 0.95)

    def test_different_people_with_similar_names(self):
        """Different people with same surname or partial similarity should NOT score high."""
        plan = [FieldComparison("name", "phonetic", 1.0)]
        # Ramesh Kumar vs Rahul Kumar (same surname, different first name)
        res = score_pair({"name": "Ramesh Kumar"}, {"name": "Rahul Kumar"}, plan)
        self.assertLessEqual(res.confidence, 0.55)

        # John Smith vs Alice Wonderland
        res_diff = score_pair({"name": "John Smith"}, {"name": "Alice Wonderland"}, plan)
        self.assertEqual(res_diff.confidence, 0.0)

    def test_missing_and_blank_fields_handling(self):
        """Missing or blank fields on either side should give no evidence and be excluded from weighted average."""
        record_a = {
            "name": "Fatima Patel",
            "email": "",  # Blank
            "phone": "+91 92792 45222",
            "city": "Mumbai",
        }
        record_b = {
            "name": "Fatima Patel",
            "email": "fatima.patel@example.com",
            # phone is completely missing from record_b
            "city": "Mumbai",
        }
        plan = [
            FieldComparison("name", "phonetic", 0.5),
            FieldComparison("email", "edit_distance", 0.2),
            FieldComparison("phone", "normalized_phone", 0.2),
            FieldComparison("city", "exact", 0.1),
        ]

        result = score_pair(record_a, record_b, plan)
        # Only 'name' and 'city' should be in field_scores
        self.assertEqual(set(result.field_scores.keys()), {"name", "city"})
        self.assertEqual(result.algorithm, "phonetic+exact")
        # Weighted average denominator is 0.5 + 0.1 = 0.6.
        # Both name (1.0) and city (1.0) matched: (1.0*0.5 + 1.0*0.1) / 0.6 = 1.0
        self.assertAlmostEqual(result.confidence, 1.0, places=4)

    def test_completely_empty_or_no_overlapping_attributes(self):
        """When nothing can be compared, confidence must be 0.0 and field_scores empty."""
        record_a = {"name": "", "email": None}
        record_b = {"phone": "9999999999"}
        result = score_pair(record_a, record_b, self.sample_plan)

        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.field_scores, {})
        self.assertEqual(result.algorithm, "")

    def test_completely_unrelated_records(self):
        """Records with different information across all fields should score 0.0."""
        record_a = {
            "name": "Fatima Patel",
            "email": "fatima.patel@example.com",
            "phone": "+91 92792 45222",
            "date_of_birth": "1998-10-13",
            "pin_code": "400020",
            "city": "Mumbai",
        }
        record_b = {
            "name": "Rohan Gupta",
            "email": "rohan.gupta91@example.in",
            "phone": "9420505680",
            "date_of_birth": "1985-05-15",
            "pin_code": "560001",
            "city": "Bengaluru",
        }
        result = score_pair(record_a, record_b, self.sample_plan)
        self.assertLess(result.confidence, 0.10)
        self.assertEqual(result.field_scores["name"], 0.0)
        self.assertEqual(result.field_scores["phone"], 0.0)
        self.assertEqual(result.field_scores["date_of_birth"], 0.0)
        self.assertEqual(result.field_scores["city"], 0.0)
        self.assertEqual(result.field_scores["pin_code"], 0.0)


    def test_unknown_method_raises_error(self):
        """Unknown method in plan should raise ValueError."""
        plan = [FieldComparison("name", "magic_ai", 1.0)]
        with self.assertRaises(ValueError):
            score_pair({"name": "Alice"}, {"name": "Bob"}, plan)

    def test_zero_total_weight(self):
        """If all weights sum to zero, confidence must be 0.0."""
        plan = [FieldComparison("city", "exact", 0.0)]
        result = score_pair({"city": "Mumbai"}, {"city": "Mumbai"}, plan)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.field_scores["city"], 1.0)

    def test_customer_records_real_pairs(self):
        """Verify score_pair on real pairs from customer-records.csv."""
        # Pair from dataset: R0102 (Naveen Bhat) and R0144 (N. Bhat)
        r0102 = {
            "name": "Naveen Bhat",
            "email": "naveen.bhat60@example.net",
            "phone": "93371 62778",
            "city": "gurgaon",
            "pin_code": "",
            "date_of_birth": "11-Jul-1965",
        }
        r0144 = {
            "name": "N. Bhat",
            "email": "naveen.bhat60@example.net",
            "phone": "09337162778",
            "city": "gurgaon",
            "pin_code": "",
            "date_of_birth": "11.07.65",
        }
        result = score_pair(r0102, r0144, self.sample_plan)
        # pin_code is missing in both, so it gives no evidence.
        self.assertNotIn("pin_code", result.field_scores)
        # All other fields match or score very highly
        self.assertGreater(result.confidence, 0.95)
        self.assertEqual(result.field_scores["phone"], 1.0)
        self.assertEqual(result.field_scores["email"], 1.0)
        self.assertEqual(result.field_scores["date_of_birth"], 1.0)
        self.assertEqual(result.field_scores["city"], 1.0)
        self.assertGreaterEqual(result.field_scores["name"], 0.90)


if __name__ == "__main__":
    unittest.main()
