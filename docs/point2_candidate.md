# Point 2 candidate, reissued attachment

Base: e43cf49236ecaae73ebe7d05895ea9c28622de2b.
This reconstructed attachment is not byte-identical to the earlier temporary ZIP.
It retains the same target modules and fixes; new offline tests were rerun.
It is separate from the earlier unaccepted 9-file pipeline/reconciliation package.

## Changes
- commission_amount and commission.amount supported; conflicts stop; zero stays zero,
  missing stays unknown; product-line commission is not multiplied by quantity.
- FBS/FBO source-scoped transactional replacement, row/date checks and bounded pagination.
- Stock collection before writing, sum repeated stock components, preserve snapshot on error,
  reject empty snapshots, unknown SKU mappings/types and >20% row-count drops.
- Validate financial IDs, amounts/dates and use unit_number; no arbitrary first-SKU assignment.
- Replace payouts only for complete returned periods; stable IDs and no stale index tail.
- Errors propagate from returns, ratings and ads; stopped campaigns included in historical ads.
- Archive flags change only for returned offers; partial failures do not reset all flags.
- Missing accrual-types client method and standalone app import path repaired.
- Validate monthly report period and file headers before replacing rows.
- Existing assertions are not weakened: two test fixtures receive newly required date fields.

## Preparation checks in this reissue
102 offline tests passed on new helpers and selected proposed replacement entry functions.
All 16 transformation rules compile against structural fixtures, not an actual full checkout.
The full existing repository suite has NOT run on this package in the assistant environment.
A full source tree build against exact base blob SHAs is still required.

## Build behavior
The builder reads immutable git objects for the base, verifies 16 reviewed blob SHAs and
all payload checksums, transforms and compiles changed Python in memory, then creates a
complete isolated candidate tree in a new sibling directory. It never checks out a branch,
stages/commits/pushes, installs dependencies or runs any live data loader/publisher.
By default full pytest tests/ is run there with selected credentials removed from the child
environment and Python socket connections blocked. Logs/JSON/diff are in _point2_review.
This is not a general-purpose OS security sandbox.

## Conservative limits
No live APIs, live DB migration, historical duplicate cleanup or publishing were tested.
Missing accruals/returns do not authorize deleting historical records.
Payout dates retain period_end because legacy raw payments lack actual bank dates;
positive payments/reversals and repeated detail periods stop for explicit review.
Empty catalogue/stocks/whole-ad snapshots and unknown contracts stop instead of erasing data.
The non-authoritative stock change log runs after commit and may report warnings.
No new cross-process lock or whole-pipeline transaction is included.
Successful helper tests do not imply acceptance of the whole project or point 2.
