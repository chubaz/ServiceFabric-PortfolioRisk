# KP-04: Capability Catalogue, Agent Roles, and Thesis Traceability

Status: draft; review requested. Implementation status: partial. Draft deadline: T+14h; review deadline: T+17h.

## Scope and implementation boundary

A capability is a finite, declared function with an input/output contract and allowed and denied effects. An agent is a role with explicit capability grants; it is not a general authority to act. Findings and alerts remain separate output identities. The capability catalogue and role cards below are implemented in their owning capability/agent lane; this document is the planning interpretation of that evidence. This document neither invokes a capability nor creates a new execution path outside the canonical ServiceFabric runtime.

## Capability catalogue

| Capability | Verified purpose | Allowed effect | Prohibited effects |
| --- | --- | --- | --- |
| `planning.knowledge.list_due` | List supplied deterministic knowledge products due by an explicit offset. | None | Order submission; broker connectivity. |
| `data.synthetic.ingest` | Expose a supplied local synthetic ingestion run. | None | Order submission; broker connectivity. |
| `portfolio.snapshot.create` | Create an immutable snapshot from supplied normalized inputs. | None | Order submission; broker connectivity. |
| `portfolio.exposure.summarize` | Calculate deterministic exposure from a supplied snapshot. | None | Order submission; broker connectivity. |
| `market.anomaly.detect` | Detect threshold breaches in supplied synthetic observations. | None | Order submission; broker connectivity. |
| `risk.capability.news_sentiment` | Summarize supplied news evidence without fabricating observations. | Draft finding | Order submission; broker connectivity. |
| `risk.capability.market_data` | Describe supplied market-data evidence without fetching provider data. | Draft finding | Order submission; broker connectivity. |
| `risk.capability.portfolio_exposure` | Describe supplied exposure evidence without calculating analytics. | Draft finding | Order submission; broker connectivity. |
| `risk.capability.alert_recommendation` | Draft a review-required, non-advisory alert from supplied evidence. | Draft alert | Order submission; broker connectivity. |

All catalogue entries require evidence and human review by default. The Day 0 implementation does not fetch a provider, submit an order, connect to a broker, rebalance automatically, or call an external LLM.

## Four agent role cards

### News & Sentiment Agent — `risk.agent.news_sentiment`

Purpose: summarize supplied news evidence. Grant: `risk.capability.news_sentiment`. Inputs are a capability invocation and evidence references; output is a bounded capability outcome. It must escalate missing, partial, stale, or consequential findings. It cannot trade, submit orders, connect to a broker, or rebalance.

### Market Data Agent — `risk.agent.market_data`

Purpose: invoke the registered synthetic-ingestion and anomaly capabilities. Grants: `data.synthetic.ingest` and `market.anomaly.detect`. Inputs are synthetic-ingest or anomaly requests plus evidence references; output is a capability result. It must surface quality limitations and escalate incomplete or consequential results; it cannot obtain live provider data.

### Portfolio Exposure Agent — `risk.agent.portfolio_exposure`

Purpose: invoke the registered snapshot and exposure capabilities. Grants: `portfolio.snapshot.create` and `portfolio.exposure.summarize`. Inputs are snapshot or exposure requests plus evidence references; output is a capability result. It may work only on supplied data and cannot execute a trade or alter an existing immutable snapshot.

### Alert & Recommendation Agent — `risk.agent.alert_recommendation`

Purpose: draft a review-required, non-advisory alert. Grant: `risk.capability.alert_recommendation`. Its output is a draft capability outcome, not investment advice, recommendation execution, or an order. Missing evidence, uncertainty, and any consequential next step require escalation to a human reviewer.

## Capability-to-agent matrix

| Capability | News & Sentiment | Market Data | Portfolio Exposure | Alert & Recommendation |
| --- | --- | --- | --- | --- |
| `planning.knowledge.list_due` | — | — | — | — |
| `data.synthetic.ingest` | — | Granted | — | — |
| `portfolio.snapshot.create` | — | — | Granted | — |
| `portfolio.exposure.summarize` | — | — | Granted | — |
| `market.anomaly.detect` | — | Granted | — | — |
| `risk.capability.news_sentiment` | Granted | — | — | — |
| `risk.capability.market_data` | — | — | — | — |
| `risk.capability.portfolio_exposure` | — | — | — | — |
| `risk.capability.alert_recommendation` | — | — | — | Granted |

An em dash means no grant. An agent must reject a capability outside its row-card grant; it may not infer a grant merely because the capability exists in the catalogue.

## Thesis deliverable traceability

| Deliverable | Thesis | Evidence | Assumptions and limitations |
| --- | --- | --- | --- |
| Capability catalogue | Bounded descriptors make permitted and prohibited behavior inspectable. | `CAPABILITY-CATALOG` | The descriptor is not itself an invocation or proof of output correctness. |
| Role cards and matrix | Explicit grants constrain coordination to a reviewed surface. | `AGENT-ROLES` | The canonical runtime must remain the only invocation path. |
| Draft findings and alerts | Explainability requires retained evidence, assumptions, warnings, and limitations. | `CAPABILITY-CATALOG`, `AGENT-ROLES` | Supplied evidence may be incomplete, synthetic, stale, or unsuitable for a conclusion. |

The structured seed entry `KP-04-T1` preserves this thesis, its source references, its runtime assumption, and its limitation.

## Human review, explainability, and prohibited effects

Every role requires human review. Outputs must retain the supplied evidence references and identify assumptions, warnings, limitations, disclosures, and whether the draft was prepared or blocked. An alert is never investment advice. Prohibited effects include broker connectivity, order submission, trade execution, automatic rebalancing, direct provider access, external LLM calls, and bypassing canonical ServiceFabric invocation/result contracts. A human may review a draft; a draft may not act on the human’s behalf.
