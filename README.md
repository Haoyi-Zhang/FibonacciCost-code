# cost-cascades

**Cost Decreases Trigger Tight Fibonacci Cascades in Saturated Cost Partitioning**

This repository studies action-cost changes between searches with fixed
labelled abstractions, fixed goals, and one fixed saturated-cost-partition
order. The production implementation uses exact integer arithmetic; a separate
implementation-independent checker uses exact rational arithmetic. No external
datasets or solvers are used.

The central results are:

- a degree-two path relay where one decrease changes every table;
- a one-table 2-Lipschitz bound and a tight proof that a unit decrease cannot
  amplify during the first two tables;
- a tight support-two envelope: after `2k+3` two-state tables the largest
  possible residual difference is `F_(k+3)`;
- a degree-three Fibonacci carry construction that attains this bound while all
  `2k+3` tables change;
- a necessary-and-sufficient exact table-reuse test; and
- an ordered repair that is identical to fresh SCP rebuilding.

Complete proofs are in `proofs/results.tex` and `proofs/supplement.pdf`. The
bounded 65-source collision audit is in `proofs/literature.tex`, with structured
metadata in `literature_matrix.csv` and canonical BibTeX in
`literature/references.bib`.

## Supported reproduction environment

The supported and verified runtime is **Linux** (a Unix-like environment),
including native Linux, a Linux container, or Linux running inside WSL2. Use
CPython 3.10 or later **without `-O` or `PYTHONOPTIMIZE`**. The retained runs
used CPython 3.13.5 on x86-64 Linux. No Python package installation, internet
access, downloaded data, planner, or model API is needed.

The scripts intentionally use Python's Unix-only `resource` module. Native
Windows Python is therefore not supported even when its Python version is new
enough. On Windows, open a WSL2 Linux distribution, extract or copy the
repository into that Linux environment, and run the commands there with the
Linux interpreter (commonly `python3`). Do not invoke the runner with Windows
Python from PowerShell or `cmd.exe`. macOS and BSD are not claimed by this
release: although they may provide `resource`, their `ru_maxrss` units and the
full toolchain were not validated.

Run the non-destructive environment preflight from the extracted repository
root:

```sh
python reproduce.py --check-environment
```

A supported run reports Linux, Python >=3.10, optimization level zero, and the
resource-accounting semantics. An unsupported platform fails before scientific
work begins; it does not emit substitute CPU/RSS values.

## Reproduce from a clean extraction

From the extracted repository root run:

```sh
python reproduce.py --out ../cost-cascades-reproduction
```

Under WSL2, run the same command inside the Linux distribution, using `python3`
if that is the interpreter name there. The destination must not already exist.
The runner never overwrites retained primary measurements. It launches one
child at a time, each with a 40-second hard timeout. The internal A* limit
remains 100,000 expansions with an 8-second cooperative time check every 128
expansions.

Linux resource fields retain their original meanings:

- CPU fields are seconds from `time.process_time()` for the current process or
  `resource.getrusage(RUSAGE_CHILDREN).ru_utime + ru_stime` for completed
  children.
- `*_peak_rss_kib` is Linux `ru_maxrss`, in KiB. For `RUSAGE_CHILDREN` it is
  the Linux-reported child peak, not a sum of simultaneous processes; the runner
  uses one child at a time.
- Wall-clock and process measurements, including all fine-grained timing
  fields, are allowed to vary and are excluded from deterministic equality.
  No unavailable measurement is filled with zero or inferred from another
  platform.

The command performs, in order:

1. bibliography/matrix/manuscript integration validation;
2. the discriminating pilot;
3. exhaustive and sequential correctness checks;
4. the support-two transition/envelope checker;
5. an implementation-independent exact-rational boundary checker;
6. tight Fibonacci construction checks through `k=64`;
7. three bounded timing shards; and
8. deterministic reconciliation and timing comparison.

`commands.json` records arguments, exit codes, stdout, stderr, wall time, and
child CPU time. `reproduction.json` records the validated Linux environment and
final reconciliation. Generated inputs, graphs, costs, work counters, search
outcomes, solution costs, expansions, and generated-node counts must match;
timing and process measurements are retained separately and need not match.

A slower host that hits a timeout has not reproduced the campaign; partial
outputs remain for diagnosis.

## Repository map

- `src/cascades.py`: reverse Dijkstra, nonnegative saturation, exact reuse,
  ordered repair, and deterministic integer-key A*.
- `src/oracle.py`: independently written synchronous Bellman--Ford and
  label-major partition calculation; it imports none of the candidate
  shortest-path or saturation functions.
- `src/families.py`: coordinate, relay, and amplifier generators.
- `src/platform_support.py`: Linux/CPython preflight and truthful `resource`
  accounting contract; unsupported platforms fail before execution.
- `pilot.py`: smallest end-to-end discriminating cases and negative controls.
- `tests/check_all.py`: 40,095 graph/cost pairs, 98,415 Lipschitz cases,
  172,800 two-table onset cases, 1,440 sequential updates, concrete
  admissibility checks, and input validation.
- `tests/check_support_envelope.py`: finite over-approximation checks for the
  four support-two transition inequalities, the parity-induction arithmetic,
  and odd-depth Fibonacci maxima through 17 tables.
- `tests/check_amplification.py`: exact tight Fibonacci witness, degree,
  support, and bit-width checks through `k=64`.
- `tests/check_rational_model.py`: independent `Fraction`-arithmetic checks of
  the real-valued onset, support-two transition, and exact-reuse boundaries; it
  imports none of the candidate implementation.
- `tests/check_bibliography.py`: verifies 65 unique records, all-context
  supplement citation, the ten-reference main selection, matrix alignment, no
  wildcard padding, and byte-identical BibTeX copies when the full project is
  present.
- `benchmark.py`: transparent five-method, 60-case timing runner.
- `summarize.py`: per-case medians and family aggregates without case filtering.
- `make_tables.py`: data-derived manuscript tables.
- `claim_evidence_ledger.csv`: claim-to-proof/test/result map.
- `external_resources.csv`: source provenance and reading-depth record.

The standalone repository includes the proof PDF but not the complete publisher
build tree. The full project archive contains `paper/` and `paper/build.py`.

## Retained evidence

The retained correctness campaign passes:

- 40,095 exhaustive old/new cost pairs on all 495 goal-reachable total
  deterministic three-state, two-label graphs with costs in `{0,1,2}`;
- 98,415 exhaustive checks of the single-table 2-Lipschitz bound;
- 172,800 checks of the tight two-table unit-decrease bound;
- 1,849 finite support-two transition checks, 6,006 induction-arithmetic
  checks, and an over-approximating reachable envelope through 17 tables;
- 1,440 sequential mixed updates against the independent partition oracle;
- 384 concrete state/update admissibility checks and all corresponding
  consistency edges;
- relay lengths through 127; and
- nine tight Fibonacci witnesses from `k=0` through `k=64`; and
- an independent exact-rational campaign with 337,500 two-stage onset cases,
  1,849 fractional support-transition checks, and 40,095 graph/cost reuse
  pairs, including 13,689 cases where the old saturation stays feasible but
  the old table is not exact.

The zero-cost tight-SCC control is rejected, newly tight alternatives are
accepted, and the deliberately stale value/allocation mixture returns 3 where
the exact concrete cost is 2.

All 60 timing cases, three repeats, and five methods complete: 900 searches.
Full rebuilding, exact reuse, and support-only repair have identical tables,
allocations, and expansions. Summed per-case median update-plus-A* time is
40.95 ms for full rebuilding, 34.73 ms for exact reuse, and 36.69 ms for
support-only repair. Exact reuse rewrites 28.5% of materialized entries overall
but all relay entries; on relays it is 1.029 times full rebuilding. These are
bounded Python microbenchmarks, not a production-planner speed claim.

## Literature and reference integrity

The bibliography contains 65 distinct works across shortest-path/search
foundations, planning heuristics, abstraction methods, cost partitioning/SCP,
and dynamic or parametric shortest paths. All 65 are cited in the supplement's
argument. The two-page paper uses ten directly relevant works. The matrix
records 15 substantive full-paper or theorem/algorithm passes and 50
bibliographic plus relevant-passage checks. Every row has a direct scholarly
verification URL, a stable identifier where available, a source tier, a
metadata status, and the access date. Sixty-two records are verified directly;
three historical/version-sensitive records are explicitly cross-checked rather
than silently merged. The validation script rejects generic homepages, duplicate
identifiers, missing provenance fields, and manuscript/matrix drift. It is not
a machine proof of scholarly priority.

## Model and trust boundary

Every abstract vertex must be goal-reachable. Costs are nonnegative Python
integers, and graphs, goals, label identities, abstractions, and order remain
fixed. Cached tables must come from `rebuild` or `update`; the code is not a
validator for arbitrary externally fabricated `Table` objects. Values remain
bound to the saturation that preserves them.

The tight envelope proof permits finite nonnegative real costs. The production
algorithms deliberately accept integers only, while the separate exact-rational
checker exercises fractional boundary cases without floating-point tolerances or
importing the production implementation. Finite checks do not replace the
symbolic proof. The upper bound requires residual-difference support at most two
after every table. Signed allocations, infinity arithmetic, changing abstraction
sets or orders, within-search changes, floating-point arithmetic, and production
PDDL integration are outside the implementation.

The oracle is algorithmically separate from candidate Dijkstra and saturation
code, but it shares generated graph inputs. It is not an independent human
review or formal proof assistant.

## Provenance and license

New code and documentation are released under the repository MIT license.
Cited papers and publisher assets are not redistributed or relicensed.
`external_resources.csv` records verification sources, access date, integration,
and reading depth. The study and prose were developed with substantive AI
assistance in an internal research workflow; any external authorship,
contribution, AI-use, originality, or eligibility declaration requires human
review. No repository has been uploaded and no submission has been made.
