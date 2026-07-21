# KP-03: CRSP/Compustat Access and Publication Boundary

Status: draft. Deadlines: draft T+7h; review T+10h.

## Publication boundary

CRSP, Compustat, Bloomberg, RavenPack, Accern, and similar licensed extracts must never be committed to this public repository. Credentials, cookies, private endpoints, portfolio statements, provider caches, and local analytical databases are also excluded. Any local provider access uses opaque local credential references, never contract values.

## Implemented behavior

The repository policy establishes this boundary and permits only reviewed synthetic fixtures under `data/fixtures/synthetic/**`. The current Day 0 planning seeds contain policy references only; they do not contain licensed data, provider credentials, queries, or observations.

## Planned behavior

Future data-lane connectors may query approved providers only under their own access controls. A failed or incomplete query must remain failed, incomplete, or explicitly quality-flagged; it must never be converted to zero. Publication review must validate provenance, redistribution rights, and whether a fixture is labelled synthetic.

## Supervisor decision

Approval of a connector design is not approval to publish provider output. Each extract and derived artifact needs its own rights and provenance review.
