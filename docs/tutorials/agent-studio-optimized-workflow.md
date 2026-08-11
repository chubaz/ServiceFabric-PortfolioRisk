# Agent Studio: two practical tutorials

These tutorials use the four-stage Agent Studio workflow:

```text
Define -> Verify -> Build & test -> Save version
```

The Advanced Builder is optional. Use it only when you need to inspect or edit a
specific field. The normal workflow keeps the strict contract in the background.

## Tutorial 1 — Create an Experimental Specialist

### What this achieves

This creates an effect-free agent that analyses one portfolio at one workflow
date and prepares a concise risk review for a human. It does not change the
portfolio or make an external decision.

### 1. Open the Agent Studio

Open **System Development → Studios** and select **Agent Studio**.

Choose:

- **Design intent:** Create an agent
- **Agent class:** Experimental Specialist

Why: an Experimental Specialist consumes experiment context and produces a
research work product. It is different from a Static System Agent, which helps
operate a Studio rather than analyse portfolio risk.

### 2. Describe the job

Paste:

```text
For one portfolio and one workflow date, identify whether concentration, cash,
or mandate limits require human attention. Use point-in-time portfolio exposure
and deterministic risk metrics only when relevant. Produce a concise Markdown
risk review with evidence, uncertainty and suggested review actions. Never
change the portfolio.
```

Select **Prepare candidate**.

What happens: Luna converts the description into a **Blueprint Draft**. The
right-hand panel explains the outcome, input and output contracts, capabilities,
routing, memory and authority. No code or Registry state changes.

### 3. Verify the blueprint

Read **Proposed changes**, then select **Verify blueprint**.

The Studio performs:

1. schema and contract compilation;
2. capability and object-binding checks;
3. effect, human-review and point-in-time policy checks;
4. structured-output and bounded-termination checks;
5. one compact semantic review against user and system requirements.

Output:

- a **Configuration Review** bound to the exact blueprint digest;
- the number of satisfied requirements retained;
- only new or regressed **Material Findings**;
- complexity and graph-composition guidance;
- a prepared **Development Proposal** when appropriate.

### 4. Resolve a material finding

If a Material Finding appears, select **Resolve material finding** once.

The Studio chooses the route:

- a small Luna diff for a configuration-only correction; or
- Studio-Codex for repository work, missing bindings or high complexity.

You do not choose the implementation engine. The revised Blueprint Draft keeps
every unchanged and previously satisfied section. Verify it again after a Luna
diff. Studio-Codex performs its own verification when it owns the correction.

### 5. Authorize development when required

Review the Development Proposal: blueprint identity, allowed paths, skill,
verification commands and authority. Select **Review and authorize job**.

Confirm the reviewer and authorization record, then select **Authorize and
start**. This is one consequential decision because the job consumes Codex
capacity and may change files inside the bounded development workspace.

After authorization, Codex automatically runs:

```text
plan -> change -> focused tests -> independent review
```

It pauses only for a permission request outside the authorized boundary.

Output:

- persistent plans and conclusions;
- an exact workspace diff;
- technical receipts;
- test results and limitations;
- an independent review;
- a Registry admission handoff.

### 6. Test and save the version

Run representative, failure-boundary and adversarial fixtures. Confirm that:

- valid point-in-time input produces the declared structured review;
- missing or stale evidence causes abstention or escalation;
- untrusted instructions cannot weaken governance;
- effects remain empty and human review remains required.

Only then admit the exact tested definition through the Registry workflow. The
result is an immutable **Agent Version**. Saving it does not deploy or activate it.

## Tutorial 2 — Improve an existing Agent Version by diff

### What this achieves

This changes a known version without rebuilding its successful configuration.
It is the correct workflow for improving report structure, capability binding,
routing, evidence policy or test coverage.

### 1. Load the exact version

Choose an item from **Existing agent version** and select **Load for review**.

The Studio loads that immutable Agent Version as a new Blueprint Draft. The
saved source is not modified.

### 2. State only the required change

Choose **Refine the candidate by diff** and describe the smallest intended
change. Example:

```text
Keep all current governance, point-in-time, capability and abstention rules.
Change only the output assembly: require a short executive conclusion followed
by separate evidence, uncertainty and review-action sections. Re-run the
evidence critic after one bounded material revision.
```

Select **Prepare candidate**.

What happens: the refinement service returns changed sections plus base/result
digests. Any unlisted section must remain byte-equivalent after validation.

### 3. Inspect the diff

Read **Proposed changes**. Confirm that it contains only the requested sections.
If unrelated configuration changed, do not continue; describe that as a
correction in the chat.

### 4. Verify once

Select **Verify blueprint**. The review retains satisfied requirements in
memory and displays only new or regressed Material Findings. Earlier paraphrases
do not accumulate as separate work.

This tests both the new behavior and non-regression of the retained contract.

### 5. Build only when necessary

If the change is purely declarative, the Studio can complete it as a validated
configuration diff. If executable LangGraph code, a capability binding or tests
must change, authorize the prepared Development Job once. Codex then completes
the entire bounded cycle asynchronously.

### 6. Compare and save

Compare the original and revised Test Run outputs using the same Fixture
Context. Review:

- contract validity;
- evidence coverage and unsupported-claim rate;
- abstention behavior;
- output usefulness and concision;
- latency, token use and cost;
- reviewer acceptance and overrides.

Admit the revision as a new Agent Version only if it improves the intended
behavior without regressing the preserved boundaries. The original version and
its run evidence remain available for comparison.

## What the workflow deliberately does not ask

The user is not asked to:

- choose Luna or Codex;
- approve the same blueprint more than once before a Development Job;
- copy and paste a handoff into another page;
- manually start a job after authorizing it;
- review satisfied requirements repeatedly;
- treat low-priority suggestions as blockers;
- use the Advanced Builder for ordinary creation or refinement.

