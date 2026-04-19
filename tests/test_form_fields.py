from __future__ import annotations

import unittest

from core.form_fields import get_field_value, normalize_form_payload


class FormFieldsTests(unittest.TestCase):
    def test_normalize_form_payload_merges_nested_and_top_level_fields(self) -> None:
        payload = {
            "tg_id": "123",
            "candidate_id": "77",
            "data": {
                "Name": "Aruzhan",
                "Surname": "Sapar",
            },
            "Which program are you applying for?": "Undergraduate",
        }

        normalized = normalize_form_payload(payload)

        self.assertEqual(normalized["Name"], "Aruzhan")
        self.assertEqual(normalized["Surname"], "Sapar")
        self.assertEqual(normalized["Which program are you applying for?"], "Undergraduate")
        self.assertNotIn("tg_id", normalized)
        self.assertNotIn("candidate_id", normalized)
        self.assertNotIn("data", normalized)

    def test_alias_lookup_supports_google_form_variants(self) -> None:
        payload = {
            "Name": "Aruzhan",
            "Surname": "Sapar",
            "Please specify your intended major:": "Computer Science",
            "Additional documents (Foundation)": "https://drive.google.com/file/d/abc/view",
        }

        self.assertEqual(get_field_value(payload, "first_name"), "Aruzhan")
        self.assertEqual(get_field_value(payload, "last_name"), "Sapar")
        self.assertEqual(get_field_value(payload, "major"), "Computer Science")
        self.assertEqual(
            get_field_value(payload, "additional_documents"),
            "https://drive.google.com/file/d/abc/view",
        )


if __name__ == "__main__":
    unittest.main()
