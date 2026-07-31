# Portfolio Replay and Agent Labs

This directory contains the work-in-progress interactive laboratories used to
test portfolio data access, portfolio construction, agent blueprints, agent
graphs, capabilities, and replay workflows independently.

## Local use

The application deliberately runs only on localhost and reads licensed data
from the external private-data directory. No provider data, credentials,
generated agents, or execution results belong in Git.

From the repository root, start the local service with:

```sh
apps/portfolio-risk-workbench/labs/start_live_data.sh 8766
```

Then open <http://127.0.0.1:8766/?workspace=agent>.

The launcher uses the thesis Python environment under the surrounding
`servicefabric-lab/state` directory. Override it when needed with
`PORTFOLIO_RISK_PYTHON`. Override the licensed-data location with
`PORTFOLIO_RISK_PRIVATE_DATA_ROOT`, and the generated-agent output directory
with `PORTFOLIO_RISK_AGENT_OUTPUT_ROOT`.

## Boundaries

- DuckDB queries are read-only, position-filtered, and restricted to the
  allow-listed CRSP/Compustat datasets.
- Native identifiers remain hidden unless explicitly requested.
- Synthetic scenarios are visibly labelled.
- Agent execution is effect-free and cannot trade, rebalance, or mutate a live
  portfolio.
- OpenAI requests use the local environment or macOS Keychain credential and
  set provider-side storage off.
- Generated LangGraph modules are local artifacts and are ignored by Git.

This is a testing surface, not a production trading or investment-advice
application.
