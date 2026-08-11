# STUDIO-S3 — Agent Studio system/experiment separation

- Status: in progress — foundational Static System Agent slice implemented
- Parent boundary: accepted PLATFORM-P6 structural correction
- Predecessor: STUDIO-S2 Capability Studio v1.2
- External financial effects: disabled

## Outcome

Rebuild Agent Studio over the proven conversational design, consensus,
blueprint, fixture and Studio–Codex handoff pattern from Capability Studio.
Agent Studio must make two different reusable agent classes unmistakable:

1. **Static System Agents** support System Development Studios. They have a
   narrow codebase and object scope, hold versioned instructions and skills,
   reason over supplied design context, and produce typed design artifacts or
   proposals. They do not calculate portfolio analytics and do not finalize,
   publish or activate the objects they discuss.
2. **Experimental Specialist Agents** are Registry-pinned agents composed into
   Experimental Research workflows. They interpret eligible point-in-time
   evidence, may request registered effect-free capabilities, and produce
   experiment work products under the selected authority policy.

The two classes may share the AgentBlueprint compiler, prompt, state, routing,
memory, governance, output and evaluation contracts. They must not share an
implicit authority, context, lifecycle or publication path.

## Static System Agent contract

A Static System Agent definition includes:

- one owning Studio and a bounded codebase/object scope;
- supported design intents such as explain, teach, show examples, clarify,
  assess feasibility, plan, critique and synthesize;
- versioned system instructions, Prompt Messages and PromptTemplate;
- selectable, inspectable Skills and a compact knowledge pack;
- typed input context and typed non-final design-artifact contracts;
- routing for multi-turn questions, four-option editable quizzes, open issues,
  consensus and proposal handoff;
- token, model, retry, memory and retention policy;
- explicit prohibition on direct object finalization or activation;
- evaluation fixtures for answer quality, reuse-first behaviour, scope
  adherence, unsupported claims and proposal quality.

LLM inference is the agent runtime, not a CapabilityDefinition. Interaction
with System Development state—Registry search, proposal persistence, source
inspection, Studio–Codex submission or definition admission—occurs through
typed capabilities or control-plane services with explicit receipts.

## Agent Studio flow

1. Choose **Static System Agent** or **Experimental Specialist Agent**.
2. Start from a versioned recipe, description or existing definition.
3. Discuss the design with an Agent Studio design partner that can explain
   patterns and retrieve examples without changing the blueprint silently.
4. Resolve material questions and record consensus.
5. Compile a temporary AgentBlueprint with field provenance.
6. Review and revise the blueprint, Skills, codebase scope and output contract.
7. Send the approved development brief to the development-only Studio–Codex
   gateway.
8. Load the built candidate into Agent Studio and execute Level 1–3 fixture
   review before Registry admission.

## Studio chat migration

The current Capability Studio design partner becomes the first reference
Static System Agent. Its present hard-coded prompt is retained only as a
bootstrap implementation. STUDIO-S3 migrates it to a versioned Registry-backed
AgentBlueprint without changing the accepted Capability Studio interaction.
Different approved versions may be selected or routed by design intent. The
selection and exact version are shown in every model receipt.

The same pattern can later serve Workflow, Dashboard, Report, Package,
Portfolio & Mandate, Scenario and Provider Studios. Each owning Studio controls
its object contract and final approval; a chat agent can only create a non-final
proposal plus a proposed capability set.

## Studio–Codex boundary

Agent Studio sends only a human-approved, schema-valid development brief to the
development-only gateway defined in
`docs/workplans/platform-development/studio-codex-gateway.md`. The brief pins
the agent class, codebase scope, Skills, contracts, fixtures and verification
commands. Codex may implement the candidate in an isolated worktree, but merge,
registration and activation remain separate reviewed transitions.

## First visible slice

1. Add the two agent-class choices before recipe selection.
2. Add one Registry-backed Static System Agent recipe for Studio design help.
3. Separate static-agent output contracts from experimental risk outputs.
4. Make Skills and codebase scope visible and reviewable for Static System
   Agents.
5. Reuse the Capability Studio chat/quiz/consensus UX and proposal-only handoff.
6. Add Codex brief generation and post-build candidate loading without claiming
   that a candidate is published.
7. Run one isolated design fixture and one experimental specialist fixture,
   displaying their different context, authority, calls and outputs.

### Slice 1 implementation note — 2026-08-09

Implemented the class boundary, versioned `Agent Studio Architect@0.1.0`,
class-specific contracts and capabilities, visible Static System scope, a
deterministic design-contract fixture, exact advisor identity receipts, and the
repository-local `build-servicefabric-agent` Codex skill. Studio–Codex execution
remains honestly disabled pending P12; this slice prepares its approved bounded
brief rather than simulating a worktree or Registry transition. Multi-turn quiz
and consensus migration plus post-build candidate loading remain in subsequent
STUDIO-S3 slices.

### Slice 2 implementation note — 2026-08-09

Loaded the Registry-backed Agent Studio Architect into Overview → Studios →
Agent Studio as the default design companion. One bounded model call prepares
a complete candidate blueprint, while the page explains only consequential
configuration, shows a before/after diff and requires a separate compiler pass
before the user can apply it to the local Agent Builder draft. The discussion
and unapplied candidate survive workspace navigation in local browser storage.
Applying does not write the Registry or activate an agent. The page also
prepares a goal/context/constraints/done-when Studio-Codex brief and supports
reviewing a pasted Codex handoff in a later refinement turn. Additional
Registry-backed Static System Agents can appear as reviewers; multi-agent
critique execution remains a subsequent slice rather than being simulated.

### Slice 3 implementation note — 2026-08-10

The experimental run path now compiles capability results into a versioned
semantic fact ledger before interpretation, deterministically verifies
availability and numerical consistency after drafting, and preserves the
field-level verification as a run artifact. Controlled fixtures are separated
from historically calibrated synthetic inputs; the latter retain only derived
in-sample parameters, reserve a named OOS window and keep licensed rows out of
run storage. The test surface now offers deterministic, Luna and one-input
comparison modes. Explicitly retained results enter the existing governed
Artifact Repository and no longer clutter the temporary Agent Studio queue.
The staged behaviour programme is maintained in
`docs/workplans/platform-development/agent-behaviour-evolution.md`.

### Slice 4 implementation note — 2026-08-10

Agent Studio now provides one lifecycle from conversational candidate to the
same Full Builder blueprint. A review action dry-compiles the LangGraph,
checks a deterministic user/system requirement ledger, scores configuration
complexity, and asks Luna for a compact semantic assessment. Material findings
can be placed directly into a reviewed refinement prompt. Continue validates
and opens the Full Builder immediately, then performs comparison and Luna
review in the background and prepares—but does not approve or execute—the
Studio–Codex proposal.

The Full Builder exposes the same review, a three-tier version-memory policy,
and exact-name/version summaries of retained tests and runs. Complete
transcripts and artifacts remain reference-only to control model input size.
Existing templates and local saved definitions can be loaded as new review
candidates without changing the source version. Studio–Codex is pinned to
`gpt-5.6-terra` with `high` reasoning for read-only engineering review;
implementation, Agent Graph promotion, save and Registry admission remain
explicit human decisions. Dedicated review, test and graph-design Codex skills
now complement the build skill.

## Exit gates

1. Every saved agent has an explicit immutable agent class and version.
2. Static agents cannot invoke portfolio-compute capabilities or finalize
   System Development objects.
3. Experimental agents cannot access Studio source/code context.
4. Skills, knowledge, prompt, model and codebase scope are inspectable and
   included in receipts.
5. Chat refinement never writes the Agent Registry or another Studio backlog;
   only explicit approval creates a proposal.
6. Studio–Codex receives only approved scoped briefs and returns a candidate,
   never an implicitly active definition.
7. Level 1–3 fixture reviews pass for both agent classes.
8. Focused contract, API, runtime, lifecycle and browser checks pass.
