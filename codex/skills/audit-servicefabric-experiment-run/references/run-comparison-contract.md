# Retained experiment-run comparison contract

## Authority boundary

Only an active or archived `ArtifactManifest` with `kind=retained_run` is an
eligible run bundle. The repository verifies every declared content digest.
Temporary Agent Studio folders are candidates for admission, not experiment
evidence.

## Comparison dimensions

The v1 gate understands these planned variable dimensions:

- `agent_definition`
- `as_of`
- `baseline_step`
- `data_truth`
- `execution`
- `information_regime`
- `input`
- `portfolio`
- `scenario`

These controls must not vary inside a pair:

- `run_group`
- `research_question`
- `risk_outcome_definition`
- `metric_definition`
- `output_contract`

`run_group` and `output_contract` are required for pair comparability.
Every planned variable must also be present on both runs and must actually
change; a failed treatment manipulation is a blocker, not a harmless warning.
Research-question, risk-outcome, and metric identities may be absent from an
older mechanically comparable pair, but their absence prevents thesis
readiness.

## Thesis-design identity

Both runs must explicitly declare the same research-question,
risk-outcome-definition, and metric-definition identities. Both must explicitly
declare their baseline step and information regime; those two may differ only
when predeclared as planned variables.

Derived file digests may establish that inputs or provenance were held constant
for a mechanical comparison. They do not replace an explicit information-regime
identity for thesis readiness.

## File coverage

The output union covers every manifest-declared logical path from both runs.
Each path has one of four states:

- `same`: path, role, and content digest match;
- `changed`: the path exists in both bundles but role or digest differs;
- `left_only`: declared only by the baseline;
- `right_only`: declared only by the counterfactual.

A changed file is not automatically a confound. Comparability is decided from
the extracted dimensions and the predeclared variable set. File statuses exist
to make the evidence difference complete and inspectable.

## Acceptance semantics

- `accepted`: allowed only when `thesis_ready=true`.
- `revision_required`: the pair is mechanically comparable but lacks explicit
  experimental-design identity.
- `rejected`: integrity failed, a required control changed, an undeclared
  dimension changed, or no counterfactual dimension changed.

An acceptance record is immutable and references both source artifacts plus
the comparison digest. A later cycle names the previous acceptance artifact in
its supersession chain. It never rewrites the prior verdict.
