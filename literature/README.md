# Bibliography provenance and version policy

`references.bib` is the canonical 65-record bibliography. `../literature_matrix.csv`
records why each work is in scope, its reading depth, a direct verification source,
a stable identifier, and any edition-level ambiguity. `../external_resources.csv`
mirrors the scholarly URLs for provenance accounting.

Source tiers are deliberately explicit:

- `publisher_or_doi`: publisher landing page or DOI resolver;
- `official_proceedings_or_journal`: venue or journal record/PDF;
- `author_or_institutional_copy`: an author-hosted or university-hosted paper copy;
- `institutional_bibliography`: a university repository or author publication record
  used where no stable publisher page was available.

`verified` means that the recorded title, authorship, year, venue, and the passage
used for positioning were checked against the listed source. `version_cross_checked`
means that two legitimate records expose different edition metadata and the selected
version is stated rather than silently merged.

Two historical cases matter:

1. **Edelkamp 2001.** The AAAI-hosted Book One proceedings copy is paginated
   84--90. ECP pre-proceedings and later bibliographies also cite 13--24. The
   project uses the AAAI proceedings copy and records the alternate pagination.
2. **Edelkamp/MoChArt.** The workshop was held in 2006, while Springer formally
   published the LNAI 4428 chapter in 2007. The BibTeX year is therefore 2007 and
   the book title keeps “MoChArt 2006.”

The 2025 *Merging Cartesian Abstractions* record also has a one-page terminal
range discrepancy across publisher/repository exports; the DOI, title, authors,
and proceedings identity agree, and the matrix states which pagination is retained.

The automatic bibliography check validates internal consistency and provenance
fields. It cannot prove global novelty, replace source reading, or certify that no
uncatalogued equivalent result exists.
