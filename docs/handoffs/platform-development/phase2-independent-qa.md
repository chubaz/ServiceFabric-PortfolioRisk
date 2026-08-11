# Phase 2 clean-worktree acceptance review

- Lane: P2-05 independent QA
- Candidate: `b8eacc67ca9344944631c425e133c639395df9cf`
- Baseline: `9440bbaeb3f43f04ff259dbde0eb2824b7f9c6f1`
- Verdict: PASS
- Review environment: fresh worktree with pinned ServiceFabric submodule

## Scope reviewed

The exact candidate was reviewed as a generated-output repository, not as a
second definition registry or experiment runtime. The review covered strict
manifest and receipt contracts, content addressing, explicit legacy-run
admission, point-in-time data-truth and rights labels, inert file preview,
download policy, archive/restore, recoverable tombstones, shared-blob
ownership, manual finalization, restart/retry behavior, API path opacity, the
Artifacts workspace, and Phase 0/1 application regressions.

## Preserved pre-acceptance defect

The earlier implementation candidate `1897d30` was not accepted. Adversarial
review found that file IDs derived only from byte digest, so two logical files
with identical bytes could resolve to the wrong file. It also found that a
recoverably tombstoned artifact must continue to own a shared blob, source
admission must recheck its complete observation after preview, and a crash
after terminal receipt commit must leave final byte cleanup exactly retryable.

Candidate `b8eacc6` binds file IDs to logical path plus digest, rechecks source
inventory/signatures/digests, counts every non-deleted owner, commits terminal
state before cleanup, and permits only an exact post-commit cleanup retry.
Regression tests exercise each repair.

## Verification evidence

- `make verify-platform-phase2` — PASS: 19 focused control-plane, artifact,
  migration and API tests plus environment, repository, package and diff gates.
- Manifest digest verification — PASS.
- JavaScript syntax verification — PASS.
- Clean worktree and exact candidate check — PASS.
- Integration regression run recorded separately: 135 artifact, application,
  Phase 0, Phase 1 and Phase 2 tests passed; the current application-only and
  control-plane repeat passed 123 tests.
- Browser verification at `?workspace=artifacts` — PASS: correct development
  truth strip, catalogue load, verified detail, opaque file identity, and inert
  escaped-text Markdown preview.

## Safety verdict

No repository endpoint executes an artifact, query, model, agent, workflow, or
financial effect. Licensed real runs remain restricted and their raw input,
activity, capability-execution, and transcript files deny browser preview and
download. API payloads expose no artifact repository or legacy source path.
Immediate legacy-folder deletion is disabled. Ordinary deletion remains
previewed, expected-revision guarded, recoverable for seven days, reference
aware, and unavailable to published or evidence-locked artifacts.

## Accepted limitations

- This is a local development repository, not production object storage,
  publication, deployment, experiment scheduling, or automatic cleanup.
- Existing Agent Lab folders remain separate sources after admission; the
  repository does not silently delete or rewrite them.
- The local OS account remains inside the trust boundary. Digests detect
  inconsistent modification but are not remote attestations.
- A corrupted committed catalogue fails closed and makes the repository
  unavailable for mutation until a later maintenance procedure repairs it.

## Conclusion

The exact candidate satisfies the Phase 2 exit boundary. No Phase 3 work is
included. The candidate is accepted for the pull-request lifecycle.
