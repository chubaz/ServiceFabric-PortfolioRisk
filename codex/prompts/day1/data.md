# Day 1 data lane prompt template

Lane: data; branch: `feature/day1-data`. Own only declared data/connectors/schema
test directories and the exact handoff.

Acceptance: local CSV/YAML validation, immutable snapshot lineage, fixed
reviewed views, query manifests, provenance, rights/access/zone/freshness and
quality flags are explicit; every external provider is disabled by default.
Exclude arbitrary SQL, provider calls, credentials, licensed/personal Git
data, broker paths, and app edits. Run focused data tests and `git diff
--check`, record evidence, commit a focused candidate, and stop without merge.
