# Day 1 information architecture

Global navigation: Dashboard, Portfolio, Risk, Findings, Alerts, Data,
Providers, Research, Notebooks, Agents, Plan, Settings. The active profile and
synthetic/private/public, freshness, and human-review badges are persistent.

Screens use server-rendered semantic HTML and are composed from semantic landmarks, reusable cards, sortable tables,
badges, disclosure panels, empty states, evidence drawers, and review forms.
Actions have visible confirmation and keyboard focus. Numerical values use
currency, percentage, date, and missing-value formatting appropriate to their
contract; missing is never silently displayed as zero. JSON endpoints remain
available under `/api` for developers and evidence inspection.

Research and notebook screens are catalogues. A notebook item may show owner,
methodology, inputs, evidence, and execution status, but cannot execute code.
The personal profile defaults to local private state and has no publication or
broker route.
