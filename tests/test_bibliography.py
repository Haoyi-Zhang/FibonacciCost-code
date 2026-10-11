"""Small in-memory regressions for content-based bibliography synchronization."""
from __future__ import annotations

import copy
import importlib.util
import re
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "bibliography_check", ROOT / "tests" / "check_bibliography.py")
assert spec is not None and spec.loader is not None
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class BibliographyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (ROOT / "literature" / "references.bib").read_text(encoding="utf-8")
        self.entries = gate.parse_bib_entries(self.text)
        self.selected = (ROOT / "literature" / "main-citations.txt").read_text(encoding="utf-8").split()

    def test_canonical_selection(self) -> None:
        gate.check_records(self.entries, self.selected)

    def test_formatting_does_not_lock_bibliography(self) -> None:
        formatted = gate.parse_bib_entries(self.text.replace("\n", "\n    "))
        key = next(k for k, fields in formatted.items() if fields.get("doi"))
        formatted[key]["doi"] = "https://doi.org/" + formatted[key]["doi"]
        formatted[key]["title"] = "{" + formatted[key]["title"] + "}"
        gate.compare_bibliographies(self.entries, formatted)

    def test_changed_title_or_doi_rejected(self) -> None:
        for field in ("title", "doi"):
            altered = copy.deepcopy(self.entries)
            key = next(k for k, fields in altered.items() if fields.get("doi"))
            altered[key][field] += " changed"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "content differs"):
                gate.compare_bibliographies(self.entries, altered)

    def test_undefined_selected_key_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "undefined"):
            gate.check_records(self.entries, self.selected + ["undefined_fixture_key"])

    def test_duplicate_bibkey_rejected(self) -> None:
        starts = list(re.finditer(r"(?m)^@\w+\{", self.text))
        first = self.text[starts[0].start():starts[1].start()]
        with self.assertRaisesRegex(ValueError, "duplicate BibTeX key"):
            gate.parse_bib_entries(self.text + first)

    def test_duplicate_title_and_doi_rejected(self) -> None:
        keys = [k for k, fields in self.entries.items() if fields.get("doi")]
        for field in ("title", "doi"):
            altered = copy.deepcopy(self.entries)
            altered[keys[1]][field] = altered[keys[0]][field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "duplicate"):
                gate.check_records(altered, self.selected)

    def test_literal_inputs_and_comments(self) -> None:
        texts = {"main.tex": r"\input{body}" + "\n% " + r"\cite{ignored}",
                 "body.tex": r"\citep[Section 2]{one,two} $a\iff b$"}
        with patch.object(Path, "is_file", side_effect=lambda: True), \
             patch.object(Path, "read_text", autospec=True,
                          side_effect=lambda path, **kwargs: texts[path.name]):
            found = gate.sources(ROOT, "main.tex")
        self.assertEqual(set(found), {"main.tex", "body.tex"})
        self.assertEqual(gate.citation_keys("\n".join(found.values())), {"one", "two"})

    def test_missing_input_rejected(self) -> None:
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(ValueError, "missing TeX input"):
                gate.sources(ROOT, "main.tex")

    def test_nocite_rejected(self) -> None:
        with patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "read_text", return_value=r"\nocite{*}"):
            with self.assertRaisesRegex(ValueError, "nocite"):
                gate.sources(ROOT, "main.tex")


if __name__ == "__main__":
    unittest.main()
