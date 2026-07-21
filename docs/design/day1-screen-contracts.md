# Day 1 screen contracts

| Screen | Required content | Safe interaction |
| --- | --- | --- |
| Dashboard | profile, data state, review queue, key cards | navigate to evidence |
| Portfolio | input preview, validation errors, immutable snapshots, comparison | explicit confirm creates a new snapshot |
| Risk | methodology, horizon, sample, metrics, warnings | filter/display only |
| Findings and Alerts | evidence, severity, limitations, draft/review state | record human DecisionPoint |
| Data and Providers | source, rights/access, zone, freshness, quality, provenance | view fixed query manifests |
| Research and Notebooks | catalogue metadata and reviewed links | no arbitrary execution |
| Agents | role/capability timeline and output digest | inspect evidence; no effects |
| Plan and Settings | workplan, profile, opaque secret references | no provider enablement or trading |

Every screen has a semantic heading order, labelled controls, keyboard path,
responsive layout, empty/error state, and visible synthetic/profile/review
status. Evidence drawers disclose source, snapshot/revision, assumptions,
warnings, and limitations.
