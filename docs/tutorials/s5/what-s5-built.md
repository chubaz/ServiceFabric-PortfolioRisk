# What S5 built in plain language

S5 created the labelled pieces that must be sealed before an experiment can
run. Think of the complete object set as a locked research case containing six
folders.

## 1. Test brief

The Scientific Design Pack says what question is being asked, what result would
support or contradict the hypothesis, which baseline is being used, what
information is available, what counts as a good or bad risk outcome, and how it
will be scored.

## 2. Portfolio rulebook

The Portfolio Governance Pack separates three things:

- the portfolio is what is held;
- the mandate explains what the portfolio is for;
- the risk policy contains the rules and thresholds used to detect a breach.

Changing a limit creates a new risk-policy version. It does not rewrite the
portfolio or mandate.

## 3. Frozen world

The World Context Pack identifies the datasets available at one time, the
portfolio-independent market environment, any scenario applied to it, the view
of that environment through the selected portfolio, and the closed relationship
graph. Information that arrived later is rejected.

## 4. Permitted toolbox

The Resource Envelope lists every capability, dataset permission, connector and
model route that the agent may reach. The agent can choose which permitted tool
to use. It cannot add an undeclared tool or dataset during the run.

## 5. Authority charter

The Authority Envelope identifies the agent, graph and workflow and says who may
propose or resolve decisions. The first teaching candidate is human-only. Its
supra-agent and external effects are explicitly disabled rather than silently
missing.

## 6. Scorecard and views

The Output and Evaluation Pack identifies the evaluation cases, repetitions and
thresholds, plus the report and dashboard definitions. Reports and dashboards
may display retained evidence but cannot introduce hidden calculations.

## The seal

The Experiment Object Set checks that every folder references the others
correctly and calculates:

- a world digest;
- a resource digest;
- an authority digest;
- an evaluation digest;
- one overall Fixture Context digest.

Repeating the same experimental arm produces the same five digests. Changing a
scenario changes the world and overall digests, but not the resource, authority
or evaluation digests. This makes controlled differences visible instead of
hiding them inside a large configuration file.

S5 defines and checks the sealed case. P7 will be responsible for opening those
references, loading the actual eligible inputs and creating the executable
Fixture Context. P8 will later execute one real bounded run against it.
