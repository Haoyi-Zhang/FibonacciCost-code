# Bibliography provenance

`references.bib` is the canonical 65-work bibliography. `../literature_matrix.csv`
records the literature audit's scope, reading depth, verification sources
and edition notes. `../external_resources.csv`
mirrors the scholarly URLs for provenance accounting.

Source tiers are deliberately explicit:

- `publisher_or_doi`: publisher landing page or DOI resolver;
- `official_proceedings_or_journal`: venue or journal record/PDF;
- `author_or_institutional_copy`: an author-hosted or university-hosted paper copy;
- `archived_primary_author_final_manuscript`: an archived copy linked by the paper's author,
  with its edition and proof dependencies recorded separately;
- `institutional_bibliography`: a university repository or author publication record
  used where no stable publisher page was available.

The metadata status `verified` refers to the recorded bibliographic identity.
Reading depth is recorded separately, with the relevant passage source in the
verification note. `version_cross_checked`
means that two legitimate records expose different edition metadata and the selected
version is stated rather than silently merged.

Two historical cases matter:

1. **Edelkamp 2001.** The AAAI-hosted Book One proceedings copy is paginated
   84--90. ECP pre-proceedings and later bibliographies also cite 13--24. The
   project uses the AAAI proceedings copy and records the alternate pagination.
2. **Edelkamp/MoChArt.** The workshop was held in 2006, while Springer formally
   published the LNCS 4428 chapter in 2007. The BibTeX year is therefore 2007;
   the formal book title is *Model Checking and Artificial Intelligence*.

The 2025 *Merging Cartesian Abstractions* record also has a one-page terminal
range discrepancy across publisher/repository exports; the DOI, title, authors,
and proceedings identity agree, and the matrix states which pagination is retained.

`main-citations.txt` lists the 52 main-text selections; the essential supplement
cites 2 works. `../tests/check_bibliography.py` checks parsed bibliography identity
and follows actual publisher inputs when available. The reading-depth fields
identify the passages examined for each cited claim. Fifty-one of the 52
main-text selections have relevant primary-body checks. These include the
complete 24-page archived author-labelled final draft of Frigioni et al.
Its fully dynamic result assumes positive edge weights; its omitted coloring
proof refers to a predecessor not covered by this reading. The author draft
has not been equated with the 31-page publisher edition. The Katz--Domshlak
journal article remains at metadata or abstract reading depth. These statuses distinguish
identity, passage support and whole-source proof review.

In `../literature_matrix.csv`, `cited_in_main` and `cited_in_supplement` refer
to the current publisher main note and publisher supplement (52 and 2 records).
`cited_in_artifact_audit` refers to the separate 65-source artifact literature
audit. Citation flags
record document inclusion, not reading depth or full-text support. The source
tiers, access dates, edition notes and reading-depth fields retain their
recorded evidence scope.
