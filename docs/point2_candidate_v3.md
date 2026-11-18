# Point 2 v3: stop dependent stages after failure

Base: e43cf49236ecaae73ebe7d05895ea9c28622de2b plus the exact 26-file v2
candidate reported with 491 passing tests and 176 subtests. v2 loaders are unchanged.

Only production change: unitka/run_finance.py.
- step still returns a boolean, but explicit False and known unsuccessful structured
  statuses are failures. Numeric 0 and ordinary None returns remain valid.
- main stops immediately when a required stage fails, rather than calculating on
  stale/partial inputs and exiting nonzero only after all nine stages.
- Successful order, date arguments, CLI flags and explicit --skip-fetch are preserved.
- Stage SystemExit/KeyboardInterrupt are not swallowed.
No financial formulas, API clients, DB schema, publisher or external scheduler changes.

The exact original orchestrator Git blob was verified before editing.
27 isolated stub-only tests: original 22 failed / 5 passed; fixed 27 passed.
Neither real loader nor calculator modules were imported in those checks.
The full repository suite for v3 has NOT run in the assistant environment.

The updater verifies v2's 26 source hashes, reads immutable raw Git objects, builds
an entirely new candidate and verifies the full diff by applying it in a temporary
tree and comparing file bytes. Existing candidate and working repository are not edited.
Full pytest tests/ then runs in the new candidate with Python network connections blocked.
No OS-wide security sandbox or production/global acceptance is claimed.
