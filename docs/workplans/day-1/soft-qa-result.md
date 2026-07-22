# Day 1 Human Soft-QA Result

Reviewer: lorenzoccasoni
Reviewed at: 2026-07-22T20:12:02Z
QA run: 20260722T140707Z
Branch: integration/day1
Reviewed head: 3c07db4dcdfa6322ad731ea185baea8267cf3d41
Decision: PASSED
Local evidence root: state/day1/soft-qa/20260722T140707Z
Evidence-manifest SHA-256: 06eccc3b65c27458473692335e53d32227e2deec2e4ce3b3c685138fc108874c
Manual-checklist SHA-256: 1642b0aa37443b8d6556eb27b9e8f86ab64e66b9361186a9517eb179db7501be

## Automated gates

Fresh remote checkout: PASS
ServiceFabric submodule pin: PASS
make verify-day1: PASS
make verify-day0: PASS
make demo-day1-headless: PASS
Independent artifact and digest validation: SKIPPED (reviewer-authorized exception; validator raised KeyError: valid on prior run)
make servicefabric-day1-smoke: PASS
ServiceFabric post-stop capability rejection: PASS
Application manifest validation: PASS
Forbidden-route inspection: PASS

## User workflows reviewed

Research profile
Personal-portfolio profile
Readable semantic dashboard and navigation
Invalid portfolio preview
Valid YAML portfolio preview
Explicit digest-bound confirmation
Idempotent repeated confirmation
Immutable corrected revision
Read-only snapshot comparison
Data quality and provenance
Provider rights and disabled access
Fixed query manifests
Reviewed risk methodologies
Tail-risk sample warning
Fixed scenario catalogue
Contribution analysis
Four-role agent timeline
HTML and Markdown reports
Alert human-review boundary
Research and notebook catalogues
Keyboard and responsive behavior
Screen-reader or accessibility-tree behavior
No-effect and prohibited-surface review

## Visual evidence

- Equivalent saved HTML/API evidence was retained; no screenshot file was recorded.

## Findings

Independent artifact validation step was intentionally skipped by the identified reviewer per authorization. The validator run failed with KeyError: valid, and this gate remains unverified.

## Accepted limitations

Synthetic or reviewed-public research evidence only.
Personal holdings remain local and private.
Historical analytics are descriptive and sample-bound.
Historical VaR and expected shortfall are not forecasts.
Fixed scenarios are linear and do not price instruments.
No FX conversion.
No real providers or external LLM.
No arbitrary SQL.
No notebook execution.
No brokerage, account, order, trade, hedge, optimization, or rebalance.
No PDF export or report-publication workflow.
This review does not impersonate supervisor approval of knowledge products.

## Merge authorization

The reviewer authorizes PR #16 to leave draft status and merge into main after every required remote check passes.
