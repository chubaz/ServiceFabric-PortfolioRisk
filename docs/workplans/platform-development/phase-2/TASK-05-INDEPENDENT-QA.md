# P2-05 — independent QA

## Objective

Review the exact Phase 2 candidate for contract reuse, storage integrity,
retention/deletion safety, run migration truth, UI clarity, and regressions.

## Only writable path

`docs/handoffs/platform-development/phase2-independent-qa.md`

## Required checks

- inspect the exact candidate and all three audit handoffs;
- attack traversal, absolute paths, symlinks, partial writes, races, digest
  collisions, undeclared/added/missing files, and metadata substitution;
- exercise archive, tombstone, restore, references, recovery deadlines, and
  final deletion, proving published/evidence-locked denial;
- verify restart persistence, idempotent admission, opaque API locators,
  bounded previews/downloads, and no execution/effects;
- test the running Artifact Repository workspace;
- run the Phase 2 gate plus full application and architecture suites;
- record PASS or exact blockers without repairing the candidate.

Stop without merging. Integration repairs blockers and requests a fresh review
of every changed candidate.
