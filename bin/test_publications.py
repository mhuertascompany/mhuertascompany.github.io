"""Regression checks for the unattended publication importer."""
import unittest
import xml.etree.ElementTree as ET

from update_publications import NS, new_records, parse_feed, read_bib


def paper(identifier="2501.12345v2", author="Marc Huertas-Company", title="A new paper"):
    entry = ET.Element("{" + NS["a"] + "}entry")
    for name, value in (("id", "https://arxiv.org/abs/" + identifier),
                        ("title", title), ("published", "2025-01-15T00:00:00Z")):
        ET.SubElement(entry, "{" + NS["a"] + "}" + name).text = value
    person = ET.SubElement(entry, "{" + NS["a"] + "}author")
    ET.SubElement(person, "{" + NS["a"] + "}name").text = author
    return entry


class PublicationsTests(unittest.TestCase):
    def records(self, entries, bib=""):
        return new_records(entries, read_bib(bib), "2024-01-01")

    def test_versions_and_existing_curated_entries_are_not_duplicated(self):
        bib = '@article{curated, title={Old title}, eprint={2501.12345}, selected={true}}'
        self.assertEqual(self.records([paper()], bib), [])

    def test_duplicate_doi_without_arxiv_id(self):
        entry = paper()
        ET.SubElement(entry, "{" + NS["arxiv"] + "}doi").text = "10.1234/TEST"
        self.assertEqual(self.records([entry], '@article{x, doi={10.1234/test}}'), [])

    def test_title_matching_ignores_case_and_braces(self):
        self.assertEqual(self.records([paper()], '@article{x, title={{A} NEW paper!}}'), [])

    def test_wrong_author_and_old_papers_are_ignored(self):
        old = paper()
        old.find("a:published", NS).text = "2023-01-01T00:00:00Z"
        self.assertEqual(self.records([paper(author="Someone Else"), old]), [])

    def test_import_is_idempotent_and_math_survives(self):
        entry = paper(author="M. Huertas-Company", title=r"Galaxies at $z > 2$ & beyond")
        records = self.records([entry, entry])
        self.assertEqual(len(records), 1)
        self.assertEqual(self.records([entry], records[0]), [])
        parsed = read_bib(records[0]).entries[0]
        self.assertIn("$z > 2$", parsed["title"])
        self.assertIn(r"\&", parsed["title"])
        self.assertEqual(parsed["arxiv"], "2501.12345")

    def test_empty_or_error_response_fails(self):
        for data in (f'<feed xmlns="{NS["a"]}"/>', "<html/>",
                     f'<feed xmlns="{NS["a"]}"><entry><id>https://arxiv.org/api/errors</id></entry></feed>'):
            with self.assertRaises(ValueError):
                parse_feed(data)

    def test_nonstandard_curated_records_are_preserved_in_parser(self):
        self.assertEqual(len(read_bib('@dataset{x, title={Data}}').entries), 1)


if __name__ == "__main__":
    unittest.main()
