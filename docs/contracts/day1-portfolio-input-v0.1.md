# Day 1 portfolio input contract v0.1

Accepted local formats are CSV and YAML. A CSV position row contains
`instrument_id`, `quantity`, and optional `currency`/`as_of`; YAML contains a
`profile`, `as_of`, `base_currency`, `positions`, and `cash_balances` mapping.
Values are parsed as Decimal, timestamps are timezone-aware UTC, and identity
and currency fields are validated before persistence.

The flow is preview -> validation (errors and quality flags visible) -> user
confirmation -> new content-addressed immutable snapshot. Invalid, incomplete,
or missing observations block confirmation and are not converted to zero. An
existing snapshot is never mutated; corrections produce a new revision. A
comparison is read-only and identifies the two snapshot IDs, changed rows,
valuation context, evidence, and limitations. Personal inputs remain outside
Git under the configured private local data root.
