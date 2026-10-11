#!/usr/bin/env python3
"""Check bibliography content and citations in included TeX sources."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_bib_entries(text: str) -> dict[str, dict[str, str]]:
    """Parse the brace/quote forms used by the supplied BibTeX files.

    The parser is intentionally small but balanced-brace aware.  Unsupported syntax
    fails closed instead of silently skipping metadata.
    """
    entries: dict[str, dict[str, str]] = {}
    pos = 0
    while True:
        match = re.search(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text[pos:], re.S)
        if match is None:
            break
        entry_type = match.group(1).lower()
        key = match.group(2)
        if key in entries:
            raise ValueError(f"duplicate BibTeX key {key!r}")
        body_start = pos + match.end()
        cursor = body_start
        depth = 1
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1
        if depth:
            raise ValueError(f"unclosed BibTeX entry {key!r}")
        body = text[body_start : cursor - 1]
        fields: dict[str, str] = {"entry_type": entry_type}
        index = 0
        while index < len(body):
            while index < len(body) and (body[index].isspace() or body[index] == ","):
                index += 1
            if index >= len(body):
                break
            field_match = re.match(r"([A-Za-z][\w-]*)\s*=\s*", body[index:])
            if field_match is None:
                raise ValueError(f"unsupported BibTeX syntax in {key!r} near {body[index:index+40]!r}")
            field = field_match.group(1).lower()
            index += field_match.end()
            if index >= len(body):
                raise ValueError(f"missing value for {key!r}:{field}")
            if body[index] == "{":
                index += 1
                value_start = index
                value_depth = 1
                while index < len(body) and value_depth:
                    if body[index] == "{":
                        value_depth += 1
                    elif body[index] == "}":
                        value_depth -= 1
                    index += 1
                if value_depth:
                    raise ValueError(f"unclosed braced value for {key!r}:{field}")
                value = body[value_start : index - 1]
            elif body[index] == '"':
                index += 1
                value_start = index
                while index < len(body):
                    if body[index] == '"' and body[index - 1] != "\\":
                        break
                    index += 1
                if index >= len(body):
                    raise ValueError(f"unclosed quoted value for {key!r}:{field}")
                value = body[value_start:index]
                index += 1
            else:
                value_start = index
                while index < len(body) and body[index] != ",":
                    index += 1
                value = body[value_start:index].strip()
            if field in fields:
                raise ValueError(f"duplicate field {field!r} in {key!r}")
            fields[field] = value.strip()
        entries[key] = fields
        pos = cursor
    if not entries:
        raise ValueError("no BibTeX entries found")
    return entries


def plain(value: str) -> str:
    return " ".join(value.split())


def title_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\\[A-Za-z]+", "", value).lower())


def doi_identity(value: str) -> str:
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "",
                  plain(value).lower())


def identity(entries: dict) -> dict:
    return {key: {"title": title_identity(fields["title"]),
                  "doi": doi_identity(fields.get("doi", "")),
                  "year": plain(fields["year"]),
                  "author": plain(fields["author"])}
            for key, fields in sorted(entries.items())}


def check_records(entries: dict, selected: list[str]) -> None:
    require(len(selected) == len(set(selected)), "duplicate selected citation key")
    require("*" not in selected and len(selected) >= 50, "main reference floor unmet")
    require(set(selected) <= set(entries), "undefined selected citation key")
    titles: set[str] = set()
    dois: set[str] = set()
    for key, fields in entries.items():
        require(all(fields.get(name) for name in ("title", "author", "year")),
                f"missing title/author/year: {key}")
        require(re.fullmatch(r"\d{4}", fields["year"]) is not None, f"invalid year: {key}")
        title = title_identity(fields["title"])
        require(title and title not in titles, f"duplicate/empty title: {key}")
        titles.add(title)
        doi = doi_identity(fields.get("doi", ""))
        if doi:
            require(doi not in dois, f"duplicate DOI: {key}")
            dois.add(doi)


def strip_comments(text: str) -> str:
    return re.sub(r"(?m)(?<!\\)%[^\n]*", "", text)


def citation_keys(text: str) -> set[str]:
    return {key.strip() for match in
            re.finditer(r"\\cite[A-Za-z]*\*?(?:\[[^\]]*\]){0,2}\s*\{([^}]*)\}",
                        strip_comments(text))
            for key in match[1].split(",") if key.strip()}


def sources(root: Path, name: str) -> dict[str, str]:
    """Follow literal inputs as TeX resolves them from the paper working directory."""
    root = root.resolve()
    found: dict[str, str] = {}
    active: set[str] = set()

    def visit(relative: str) -> None:
        path = (root / relative).resolve()
        require(path.is_relative_to(root), f"TeX input outside paper: {relative}")
        require(relative not in active, f"cyclic TeX input: {relative}")
        require(path.is_file(), f"missing TeX input: {relative}")
        if relative in found:
            return
        active.add(relative)
        text = strip_comments(path.read_text(encoding="utf-8"))
        require(not re.search(r"\\nocite\b", text), f"nocite padding: {relative}")
        controls = [m[1] for m in re.finditer(r"\\(if[A-Za-z]*|else|fi)\b", text)
                    if m[1] != "iff"]  # Mathematical iff is not a TeX branch.
        require(not controls, f"conditional input needs explicit review: {relative}")
        found[relative] = text
        for child in re.findall(r"\\(?:input|include)\s*\{([^{}]+)\}", text):
            require("\\" not in child, f"nonliteral TeX input: {child}")
            visit(child if Path(child).suffix else child + ".tex")
        active.remove(relative)

    visit(name)
    return found


def compare_bibliographies(canonical: dict, publisher: dict) -> None:
    require(identity(canonical) == identity(publisher),
            "bibliography key/title/DOI/author/year content differs")


def validate(artifact: Path, paper: Path | None = None) -> dict:
    entries = parse_bib_entries((artifact / "literature" / "references.bib").read_text(encoding="utf-8"))
    selected = (artifact / "literature" / "main-citations.txt").read_text(encoding="utf-8").split()
    check_records(entries, selected)
    main, supplement = set(selected), None
    if paper is not None:
        require(paper.is_dir(), f"paper directory missing: {paper}")
        publisher = parse_bib_entries((paper / "references.bib").read_text(encoding="utf-8"))
        compare_bibliographies(entries, publisher)
        documents = {name: sources(paper, name + ".tex") for name in ("main", "supplement")}
        keys = {name: set().union(*(citation_keys(text) for text in paths.values()))
                for name, paths in documents.items()}
        require(keys["main"] == main, "main citation-key list differs from included TeX")
        require((keys["main"] | keys["supplement"]) <= set(entries), "undefined citation in TeX")
        main, supplement = keys["main"], keys["supplement"]
    return {
        "report_scope": "bibliography_content_and_citation_selection",
        "publisher_documents_validated": paper is not None,
        "bibliography_entries": len(entries),
        "main_unique_citations": len(main),
        "supplement_unique_citations": len(supplement) if supplement is not None else None,
        "publisher_citation_keys": {"main": sorted(main),
                                   "supplement": sorted(supplement) if supplement is not None else None},
        "canonical_metadata": identity(entries),
        "scope_note": "Offline content/citation checks only. No scholarly full-text certification; absent paper sources are not validated.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-dir", type=Path)
    parser.add_argument("--out", "--output", default="-", help="default stdout; output must be a new path")
    args = parser.parse_args()
    artifact = Path(__file__).resolve().parents[1]
    neighbor = artifact.parent / "paper"
    paper = args.paper_dir if args.paper_dir is not None else (neighbor if neighbor.is_dir() else None)
    result = validate(artifact, paper)
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out != "-":
        out = Path(args.out)
        if not out.is_absolute():
            out = artifact / out
        require(not out.exists(), "refusing to overwrite an existing result")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
