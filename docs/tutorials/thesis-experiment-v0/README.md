# Experiment page guide

The research page does not run a development sample. It remains blocked until
one historical dataset, one portfolio with its rules, and three comparison
methods are connected.

## The four parts

1. **Data** — the historical period and information given to each method.
2. **Portfolio rules** — the portfolio, mandate, risk limits and allowed
   recommendations.
3. **Methods** — rules, a fixed workflow and an LLM using the same cases.
4. **Results** — warning accuracy, timing, missed risks, failures and cost.

## What happens next

Complete the items in
`docs/thesis/prototype-readiness.md`. The Run button should be enabled only when
the inputs and all three methods are connected and checked.

Automated software tests may continue to use development-only sample data. Their
outputs belong in developer logs, not on the research results page.
