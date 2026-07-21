# D0-PREP: Repository and Agent Preparation

## Objective

Create a reproducible, public, locally validated application-overlay repository
that is ready for bounded parallel Day 0 implementation.

## In scope

- local drive hierarchy;
- Git and GitHub configuration;
- public overlay repository;
- read-only ServiceFabric pin;
- public-data and secret boundaries;
- Codex safety instructions;
- baseline CI;
- branch and worktree topology;
- preparation evidence and handoff.

## Out of scope

- risk-domain implementation;
- data ingestion;
- application pages;
- portfolio calculations;
- anomaly detection;
- LLM calls;
- agent workflows;
- live provider connections;
- deployment;
- trading or order execution.

## Acceptance

- repository visibility is public;
- `main` exists and is protected;
- upstream pin matches the manifest;
- ServiceFabric doctor passes;
- repository preparation CI passes;
- Codex doctor passes;
- no secret or provider-data path is tracked;
- preparation handoff is reviewed;
- `config/agent/day0/status.json` marks preparation complete;
- `docs/workplans/current.md` points to Wave 0A;
- tag `day0-prepared` exists;
- six Day 0 worktrees are clean and based on that tag.

## Rollback

Delete the new repository only before substantive implementation begins.
Otherwise archive it and preserve the Git history and preparation evidence.
