"""Validate bibliography provenance and manuscript integration.

This checker is intentionally structural. It verifies the curated records,
source-provenance fields, cross-file alignment, citation coverage, and absence
of wildcard padding. It cannot establish global scholarly priority or replace
human reading of the cited works.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

MIN_REFERENCES = 55
EXPECTED_REFERENCES = 65
ACCESS_DATE = "2026-09-16"
EXPECTED_MAIN = {
    "scp2020", "comparison2017", "subsetsaturated2019", "transitioncp2021",
    "dstar2002", "lpa2004", "online2021", "dw2021",
    "sensitivity2024", "monotonic2026",
}
ALLOWED_DEPTH = {
    "substantive full-paper or theorem/algorithm pass",
    "bibliographic verification plus relevant cited context",
}
ALLOWED_SOURCE_TIERS = {
    "publisher_or_doi",
    "official_proceedings_or_journal",
    "author_or_institutional_copy",
    "institutional_bibliography",
}
ALLOWED_METADATA_STATUS = {"verified", "version_cross_checked"}
VERSION_CROSS_CHECKED = {"edelkamp2001", "edelkamp2006", "mergecartesian2025"}
GENERIC_OR_INDIRECT = {
    "https://mrlab.ai/jendrik-seipp/",
    "https://mrlab.ai/",
    "https://mrlab.ai/papers/seipp-et-al-jair2020.pdf",
}
REQUIRED_MATRIX_COLUMNS = {
    "bibkey", "year", "category", "title", "role_in_review",
    "specific_boundary", "verification_url", "read_depth",
    "cited_in_main", "cited_in_supplement", "canonical_identifier",
    "source_tier", "metadata_status", "verification_note", "access_date",
}


def bib_blocks(text: str) -> dict[str, str]:
    starts = list(re.finditer(r"(?m)^@(\w+)\{([^,]+),", text))
    blocks: dict[str, str] = {}
    for index, match in enumerate(starts):
        key = match.group(2).strip()
        if key in blocks:
            raise AssertionError(f"duplicate BibTeX key: {key}")
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks[key] = text[match.start():end]
    return blocks


def field(block: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^\s*{re.escape(name)}\s*=\s*\{{(.*?)\}}\s*,?\s*$", block
    )
    if not match:
        match = re.search(
            rf"(?mi)^\s*{re.escape(name)}\s*=\s*\{{([^\n]*)\}}", block
        )
    return " ".join(match.group(1).split()) if match else ""


def norm_title(title: str) -> str:
    title = re.sub(r"\\[A-Za-z]+", "", title)
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def citation_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for match in re.finditer(r"\\cite\w*(?:\[[^\]]*\])?\{([^}]*)\}", text):
        keys.update(key.strip() for key in match.group(1).split(",") if key.strip())
    return keys


def is_direct_scholarly_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    if url in GENERIC_OR_INDIRECT:
        return False
    path = parsed.path.rstrip("/")
    # Reject bare homepages: a verification source should identify a paper,
    # proceedings record, DOI, repository item, or named author bibliography.
    if parsed.netloc in {"mrlab.ai", "www.mrlab.ai"} and path in {"", "/jendrik-seipp"}:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="results/bibliography_validation.json")
    args = parser.parse_args()

    artifact = Path(__file__).resolve().parents[1]
    project = artifact.parent
    canonical = artifact / "literature" / "references.bib"
    paper_dir = project / "paper"
    paper_copy = paper_dir / "references.bib"
    provenance_readme = artifact / "literature" / "README.md"
    assert provenance_readme.exists(), "missing bibliography provenance README"

    canonical_bytes = canonical.read_bytes()
    if paper_copy.exists():
        assert canonical_bytes == paper_copy.read_bytes(), "paper/artifact bibliography drift"
    text = canonical_bytes.decode("utf-8")
    blocks = bib_blocks(text)
    assert len(blocks) == EXPECTED_REFERENCES
    assert len(blocks) >= MIN_REFERENCES

    titles: dict[str, str] = {}
    years: dict[str, str] = {}
    normalized: dict[str, str] = {}
    for key, block in blocks.items():
        title = field(block, "title")
        year = field(block, "year")
        author = field(block, "author")
        assert title and year and author, f"missing required metadata: {key}"
        assert re.fullmatch(r"\d{4}", year), f"invalid year for {key}: {year!r}"
        normalized_title = norm_title(title)
        assert normalized_title, f"empty normalized title: {key}"
        if normalized_title in normalized:
            raise AssertionError(
                f"duplicate normalized title: {key} and {normalized[normalized_title]}"
            )
        normalized[normalized_title] = key
        titles[key], years[key] = title, year

    matrix_path = artifact / "literature_matrix.csv"
    with matrix_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert set(reader.fieldnames or ()) == REQUIRED_MATRIX_COLUMNS, (
            f"matrix fields differ: {reader.fieldnames}"
        )
        matrix = list(reader)
    assert len(matrix) == len(blocks)
    matrix_keys = [row["bibkey"] for row in matrix]
    assert len(matrix_keys) == len(set(matrix_keys)), "duplicate matrix key"
    assert set(matrix_keys) == set(blocks), "matrix/BibTeX key mismatch"
    assert all(row["year"] == years[row["bibkey"]] for row in matrix)
    assert all(
        norm_title(row["title"]) == norm_title(titles[row["bibkey"]])
        for row in matrix
    )
    assert all(is_direct_scholarly_url(row["verification_url"]) for row in matrix)
    assert all(row["read_depth"] in ALLOWED_DEPTH for row in matrix)
    assert all(row["source_tier"] in ALLOWED_SOURCE_TIERS for row in matrix)
    assert all(row["metadata_status"] in ALLOWED_METADATA_STATUS for row in matrix)
    assert all(row["verification_note"].strip() for row in matrix)
    assert all(row["access_date"] == ACCESS_DATE for row in matrix)
    identifiers = [row["canonical_identifier"] for row in matrix]
    assert all(identifier.strip() for identifier in identifiers)
    assert len(identifiers) == len(set(identifiers)), "duplicate canonical identifier"
    assert {
        row["bibkey"] for row in matrix if row["metadata_status"] == "version_cross_checked"
    } == VERSION_CROSS_CHECKED
    assert all(
        row["source_tier"] != "institutional_bibliography"
        for row in matrix if int(row["year"]) >= 2024
    ), "recent records require publisher, venue, or direct author/institutional copies"
    assert all(row["cited_in_supplement"] == "yes" for row in matrix)
    assert {
        row["bibkey"] for row in matrix if row["cited_in_main"] == "yes"
    } == EXPECTED_MAIN

    literature_text = (artifact / "proofs" / "literature.tex").read_text(encoding="utf-8")
    results_text = (artifact / "proofs" / "results.tex").read_text(encoding="utf-8")
    sources = {"literature.tex": literature_text, "results.tex": results_text}
    main_path = paper_dir / "main.tex"
    supplement_path = paper_dir / "supplement.tex"
    main_text = main_path.read_text(encoding="utf-8") if main_path.exists() else ""
    supplement_text = supplement_path.read_text(encoding="utf-8") if supplement_path.exists() else ""
    if main_text:
        sources["main.tex"] = main_text
    if supplement_text:
        sources["supplement.tex"] = supplement_text
    for name, source in sources.items():
        assert "\\nocite" not in source, f"reference padding via nocite in {name}"

    literature_citations = citation_keys(literature_text)
    assert literature_citations == set(blocks), (
        f"literature citations differ: missing={sorted(set(blocks)-literature_citations)}, "
        f"extra={sorted(literature_citations-set(blocks))}"
    )
    main_citations = citation_keys(main_text) if main_text else set(EXPECTED_MAIN)
    if main_text:
        assert main_citations == EXPECTED_MAIN, (
            f"main citations differ: missing={sorted(EXPECTED_MAIN-main_citations)}, "
            f"extra={sorted(main_citations-EXPECTED_MAIN)}"
        )
    all_tex_citations = literature_citations | citation_keys(results_text) | main_citations
    assert all_tex_citations <= set(blocks), "undefined citation key in TeX sources"
    if supplement_text:
        assert "\\input{../artifact/proofs/literature}" in supplement_text

    external_path = artifact / "external_resources.csv"
    with external_path.open(newline="", encoding="utf-8") as stream:
        external = list(csv.DictReader(stream))
    scholarly = [row for row in external if re.fullmatch(r"L\d{2}", row["id"])]
    assert len(scholarly) == len(blocks)
    assert [row["id"] for row in scholarly] == [f"L{index:02d}" for index in range(1, 66)]
    for matrix_row, external_row in zip(matrix, scholarly):
        assert external_row["url"] == matrix_row["verification_url"], (
            f"external/matrix URL drift: {matrix_row['bibkey']}"
        )
        assert external_row["access_date"] == matrix_row["access_date"] == ACCESS_DATE
        assert matrix_row["source_tier"] in external_row["acquisition"]
        assert matrix_row["metadata_status"] in external_row["acquisition"]

    result = {
        "status": "passed",
        "minimum_required": MIN_REFERENCES,
        "bibliography_entries": len(blocks),
        "main_unique_citations": len(main_citations),
        "supplement_unique_citations": len(literature_citations),
        "citation_padding_command_used": False,
        "duplicate_keys": 0,
        "duplicate_titles": 0,
        "duplicate_canonical_identifiers": 0,
        "generic_or_indirect_verification_urls": 0,
        "category_counts": dict(sorted(Counter(row["category"] for row in matrix).items())),
        "read_depth_counts": dict(sorted(Counter(row["read_depth"] for row in matrix).items())),
        "source_tier_counts": dict(sorted(Counter(row["source_tier"] for row in matrix).items())),
        "metadata_status_counts": dict(sorted(Counter(row["metadata_status"] for row in matrix).items())),
        "version_cross_checked_keys": sorted(VERSION_CROSS_CHECKED),
        "access_date": ACCESS_DATE,
        "bib_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "matrix_rows": len(matrix),
        "external_scholarly_rows": len(scholarly),
        "scope_note": (
            "Structural and provenance validation only; priority, novelty, and "
            "source interpretation remain scholarly judgments."
        ),
    }
    out = Path(args.out)
    if not out.is_absolute():
        out = artifact / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
