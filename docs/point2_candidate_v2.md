# Point 2 candidate v2

Built on e43cf49236ecaae73ebe7d05895ea9c28622de2b plus the exact 24-file
candidate identified by the supplied verification.json (480 tests, 176 subtests).
The old isolated candidate is read-only input. The working source repository is
read only through immutable Git objects; no checkout/index/commit/push is performed.

Fixes: terminal returns cursor 0; required financial/ad metrics are not silently zeroed;
completely unrelated payout periods are rejected while intersecting periods are allowed;
wrong financial_data types are rejected. Existing assertions about zero-valued ad metrics
are preserved with a structurally complete fixture. The original seven failed review cases
and four compatibility/validation cases are included in the new regression test file.

113 offline tests passed during preparation on new helpers and selected replacement entry
functions. Full existing tests have NOT run on v2 in the assistant environment.
No live APIs or working databases were tested or modified.
Missing API metrics now stop for contract review rather than being treated as zero.
No changes to payment-date conventions, financial formulas or the orchestrator are included.

The updater reconstructs the complete baseline tree from raw Git objects, imports only the
24 checksum-pinned files from v1, applies embedded v2 replacements, validates Python,
generates a standard unified diff with proper no-final-newline markers, and checks/applies
that diff ONLY in a temporary baseline tree before writing the new candidate directory.
It then runs the full tests/ directory with Python network connections blocked. Results
are in _point2_review. This is not an OS security sandbox and not production acceptance.
