from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
LABS_ROOT = ROOT / "apps" / "portfolio-risk-workbench" / "labs"
sys.path.insert(0, str(LABS_ROOT))

import agent_studio  # noqa: E402
import studio_codex  # noqa: E402


class FakeTransport:
    def __init__(self) -> None:
        self.handler: Any = None
        self.turns: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []
        self.thread_count = 0

    def set_event_handler(self, handler: Any) -> None:
        self.handler = handler

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        return {
            "available": True,
            "version": "codex-cli test",
            "process_active": probe,
            "account": {"checked": probe, "authenticated": probe, "type": "test"},
        }

    def start_thread(self, *, cwd: Path) -> dict[str, Any]:
        self.thread_count += 1
        thread_id = "thread-test" if self.thread_count == 1 else f"thread-test-{self.thread_count}"
        return {
            "thread": {"id": thread_id},
            "instructionSources": [str(cwd / "AGENTS.md")],
        }

    def start_turn(
        self,
        *,
        thread_id: str,
        cwd: Path,
        prompt: str,
        phase: str,
        skill_path: Path | None = None,
    ) -> dict[str, Any]:
        turn_id = f"turn-{len(self.turns) + 1}"
        self.turns.append(
            {
                "turn_id": turn_id,
                "thread_id": thread_id,
                "cwd": cwd,
                "prompt": prompt,
                "phase": phase,
                "skill_path": skill_path,
            }
        )
        return {"turn": {"id": turn_id, "status": "inProgress"}}

    def review(self, *, thread_id: str) -> dict[str, Any]:
        return {"turn": {"id": "turn-review", "status": "inProgress"}}

    def interrupt(self, *, thread_id: str, turn_id: str) -> dict[str, Any]:
        return {}

    def respond(self, *, request_id: str | int, decision: str) -> None:
        self.responses.append({"request_id": request_id, "decision": decision})


def _proposal_request() -> studio_codex.CodexProposalRequest:
    blueprint = agent_studio.AgentBlueprint.model_validate(
        agent_studio.agent_studio_architect_template()["blueprint"]
    )
    return studio_codex.CodexProposalRequest(
        blueprint=blueprint,
        build_brief=(
            "Implement the approved Agent Studio Architect through the existing canonical "
            "agent contracts. Preserve proposal-only authority, add focused fixtures and "
            "return complete verification and traceability evidence."
        ),
        configuration_review={
            "review_id": "review-test",
            "agent_name": blueprint.name,
            "version": blueprint.version,
            "requirements": [
                {
                    "requirement_id": "REQ-001",
                    "statement": "The agent remains proposal-only.",
                    "status": "satisfied",
                    "materiality": "critical",
                    "proposed_correction": "",
                }
            ],
            "luna": {"status": "completed", "review": {"executive_assessment": "Ready."}},
        },
    )


def test_codex_proposal_must_be_approved_before_a_thread_starts(tmp_path: Path) -> None:
    transport = FakeTransport()
    manager = studio_codex.StudioCodexManager(
        transport=transport, state_root=tmp_path, repo_root=ROOT, autonomous=False
    )
    proposal = manager.create_proposal(_proposal_request())

    assert proposal["status"] == "draft"
    assert proposal["readiness_gate"]["ready_for_approval"] is True
    assert proposal["skill"]["id"] == "build-servicefabric-agent"
    assert proposal["skill_learning"] == {
        "enabled": True,
        "mode": "post_run_candidate_only",
        "skill": {
            "id": "improve-servicefabric-skill",
            "path": "codex/skills/improve-servicefabric-skill/SKILL.md",
        },
        "candidate_paths": [
            "codex/skills/build-servicefabric-agent",
            "codex/skills/design-servicefabric-agent-graph",
            "codex/skills/review-servicefabric-agent",
            "codex/skills/test-servicefabric-agent",
        ],
        "activation": "separate_human_review_required",
    }
    assert [item["id"] for item in proposal["supporting_skills"]] == [
        "review-servicefabric-agent",
        "test-servicefabric-agent",
        "design-servicefabric-agent-graph",
    ]
    assert "vendor/servicefabric" in proposal["forbidden_paths"]
    assert list((tmp_path / "proposals").glob("*.json"))

    with pytest.raises(PermissionError, match="explicit human approval"):
        manager.start_session(
            studio_codex.CodexSessionRequest(proposal_id=proposal["proposal_id"])
        )

    approved = manager.approve_proposal(
        proposal["proposal_id"],
        studio_codex.CodexProposalApprovalRequest(
            actor_id="reviewer",
            rationale="The blueprint, scope and verification boundary are acceptable.",
        ),
    )
    session = manager.start_session(
        studio_codex.CodexSessionRequest(proposal_id=approved["proposal_id"])
    )

    assert session["status"] == "planning"
    assert session["instruction_sources"] == [str(ROOT / "AGENTS.md")]
    assert transport.turns[0]["phase"] == "planning"
    assert "PLAN ONLY" in transport.turns[0]["prompt"]
    assert "$review-servicefabric-agent" in transport.turns[0]["prompt"]
    assert transport.turns[0]["skill_path"].name == "SKILL.md"
    assert transport.turns[0]["skill_path"].parent.name == "review-servicefabric-agent"
    assert session["runtime_profile"]["model"] == "gpt-5.6-terra"
    assert session["runtime_profile"]["reasoning_effort"] == "high"


def test_codex_session_requires_human_gates_and_retains_live_receipts(tmp_path: Path) -> None:
    transport = FakeTransport()
    manager = studio_codex.StudioCodexManager(
        transport=transport, state_root=tmp_path, repo_root=ROOT, autonomous=False
    )
    proposal = manager.create_proposal(_proposal_request())
    manager.approve_proposal(
        proposal["proposal_id"],
        studio_codex.CodexProposalApprovalRequest(
            actor_id="reviewer",
            rationale="The candidate is bounded and ready for a read-only plan.",
        ),
    )
    session = manager.start_session(
        studio_codex.CodexSessionRequest(proposal_id=proposal["proposal_id"])
    )

    transport.handler(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-test",
                "turn": {"id": "turn-1", "status": "completed"},
            },
        }
    )
    planned = manager.get_session(session["session_id"])
    assert planned["status"] == "awaiting_implementation_approval"

    implementing = manager.start_turn(
        session["session_id"],
        studio_codex.CodexTurnRequest(
            phase="implementation",
            instruction="Implement the accepted plan and run focused verification.",
        ),
    )
    assert implementing["status"] == "implementing"
    assert transport.turns[-1]["phase"] == "implementation"

    transport.handler(
        {
            "id": "approval-1",
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thread-test",
                "turnId": "turn-2",
                "itemId": "item-1",
                "reason": "Run the declared focused test.",
                "command": "python3 -m pytest -q tests/application/test_agent_studio.py",
            },
        }
    )
    waiting = manager.get_session(session["session_id"])
    assert waiting["pending_approvals"][0]["request_id"] == "approval-1"

    resolved = manager.respond_approval(
        session["session_id"],
        studio_codex.CodexApprovalRequest(
            request_id="approval-1", decision="accept"
        ),
    )
    assert resolved["pending_approvals"] == []
    assert transport.responses == [{"request_id": "approval-1", "decision": "accept"}]

    transport.handler(
        {
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": "thread-test",
                "turnId": "turn-2",
                "delta": "temporary streaming text",
            },
        }
    )
    streaming = manager.get_session(session["session_id"])
    assert all(item["method"] != "item/agentMessage/delta" for item in streaming["events"])
    assert streaming["live_activity"]["label"]

    transport.handler(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thread-test",
                "turnId": "turn-2",
                "item": {
                    "type": "agentMessage",
                    "text": "Implementation completed with one reusable skill observation.",
                },
            },
        }
    )
    transport.handler(
        {
            "method": "turn/diff/updated",
            "params": {
                "threadId": "thread-test",
                "turnId": "turn-2",
                "diff": "diff --git a/agent.py b/agent.py",
            },
        }
    )
    transport.handler(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-test",
                "turn": {"id": "turn-2", "status": "completed"},
            },
        }
    )
    completed = manager.get_session(session["session_id"])
    assert completed["status"] == "awaiting_review"
    assert completed["latest_diff"].startswith("diff --git")
    assert any(item["method"] == "session/approval-resolved" for item in completed["events"])
    assert any(
        item.get("payload", {}).get("item", {}).get("text", "").startswith("Implementation completed")
        for item in completed["events"]
    )
    assert completed["live_activity"] is None
    assert completed["documents"][0]["kind"] == "candidate_diff"
    assert completed["documents"][0]["content"].startswith("diff --git")

    reviewing = manager.review(session["session_id"])
    assert reviewing["status"] == "reviewing"
    assert reviewing["turns"][-1]["phase"] == "review"


def test_autonomous_job_advances_from_plan_through_independent_review(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    manager = studio_codex.StudioCodexManager(
        transport=transport,
        state_root=tmp_path,
        repo_root=ROOT,
        autonomous=True,
        background_dispatch=lambda task: task(),
    )
    proposal = manager.create_proposal(_proposal_request())
    manager.approve_proposal(
        proposal["proposal_id"],
        studio_codex.CodexProposalApprovalRequest(
            actor_id="reviewer",
            rationale="I authorize this bounded autonomous development job.",
        ),
    )
    session = manager.start_session(
        studio_codex.CodexSessionRequest(proposal_id=proposal["proposal_id"])
    )

    transport.handler(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-test",
                "turn": {"id": "turn-1", "status": "completed"},
            },
        }
    )
    implementing = manager.get_session(session["session_id"])
    assert implementing["status"] == "implementing"
    assert [item["phase"] for item in implementing["turns"]] == [
        "planning",
        "implementation",
    ]

    transport.handler(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-test",
                "turn": {"id": "turn-2", "status": "completed"},
            },
        }
    )
    reviewing = manager.get_session(session["session_id"])
    assert reviewing["status"] == "reviewing"
    assert reviewing["turns"][-1]["phase"] == "review"

    transport.handler(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-test",
                "turn": {"id": "turn-review", "status": "completed"},
            },
        }
    )
    completed = manager.get_session(session["session_id"])
    assert completed["status"] == "review_complete"
    assert completed["pending_approvals"] == []


def test_autonomous_jobs_parallelize_read_only_work_and_serialize_shared_writes(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    manager = studio_codex.StudioCodexManager(
        transport=transport,
        state_root=tmp_path,
        repo_root=ROOT,
        autonomous=True,
        background_dispatch=lambda task: task(),
    )
    first_request = _proposal_request()
    second_request = _proposal_request()
    second_request.blueprint.name = "second_bounded_agent"
    second_request.configuration_review["agent_name"] = "second_bounded_agent"
    first_proposal = manager.create_proposal(first_request)
    second_proposal = manager.create_proposal(second_request)
    for proposal in (first_proposal, second_proposal):
        manager.approve_proposal(
            proposal["proposal_id"],
            studio_codex.CodexProposalApprovalRequest(
                actor_id="reviewer",
                rationale="I authorize this bounded asynchronous Studio-Codex job.",
            ),
        )
    first = manager.start_session(
        studio_codex.CodexSessionRequest(proposal_id=first_proposal["proposal_id"])
    )
    second = manager.start_session(
        studio_codex.CodexSessionRequest(proposal_id=second_proposal["proposal_id"])
    )

    transport.handler(
        {
            "method": "turn/completed",
            "params": {
                "threadId": first["thread_id"],
                "turn": {"id": "turn-1", "status": "completed"},
            },
        }
    )
    transport.handler(
        {
            "method": "turn/completed",
            "params": {
                "threadId": second["thread_id"],
                "turn": {"id": "turn-2", "status": "completed"},
            },
        }
    )

    assert manager.get_session(first["session_id"])["status"] == "implementing"
    assert manager.get_session(second["session_id"])["status"] == "queued_implementation"

    first_implementation_turn = manager.get_session(first["session_id"])["active_turn_id"]
    transport.handler(
        {
            "method": "turn/completed",
            "params": {
                "threadId": first["thread_id"],
                "turn": {"id": first_implementation_turn, "status": "completed"},
            },
        }
    )

    assert manager.get_session(first["session_id"])["status"] == "reviewing"
    assert manager.get_session(second["session_id"])["status"] == "implementing"


def test_completed_run_can_prepare_a_separately_reviewed_skill_candidate(tmp_path: Path) -> None:
    transport = FakeTransport()
    manager = studio_codex.StudioCodexManager(
        transport=transport, state_root=tmp_path, repo_root=ROOT, autonomous=False
    )
    proposal = manager.create_proposal(_proposal_request())
    manager.approve_proposal(
        proposal["proposal_id"],
        studio_codex.CodexProposalApprovalRequest(
            actor_id="reviewer",
            rationale="The candidate is bounded and ready for a read-only plan.",
        ),
    )
    session = manager.start_session(
        studio_codex.CodexSessionRequest(proposal_id=proposal["proposal_id"])
    )
    stored = manager.get_session(session["session_id"])
    stored["status"] = "review_complete"
    studio_codex._atomic_json(manager._session_path(session["session_id"]), stored)

    improving = manager.start_turn(
        session["session_id"],
        studio_codex.CodexTurnRequest(
            phase="skill_revision",
            instruction="Use the completed run evidence to improve only reusable skill guidance.",
        ),
    )

    assert improving["status"] == "improving_skill"
    assert transport.turns[-1]["phase"] == "skill_revision"
    assert transport.turns[-1]["skill_path"] == studio_codex.SKILL_IMPROVEMENT_SKILL
    assert "$improve-servicefabric-skill" in transport.turns[-1]["prompt"]
    assert "do not activate, publish or merge" in transport.turns[-1]["prompt"]


def test_agent_studio_exposes_real_codex_provider_controls() -> None:
    html = (LABS_ROOT / "index.html").read_text()
    javascript = (LABS_ROOT / "labs.js").read_text()
    server = (LABS_ROOT / "duckdb_server.py").read_text()

    assert 'id="agent-codex-bridge"' in html
    assert "Review and authorize job" in javascript
    assert "Authorize and start" in html
    assert "await startAgentCodexSession()" in javascript
    assert "Running asynchronously" in javascript
    assert "Persistent work record" in javascript
    assert "data-codex-session-picker" in javascript
    assert "Improve skills from this run" in javascript
    assert "window.prompt(\"Reviewer ID\"" not in javascript
    assert 'id="agent-codex-approval-form"' in html
    assert "/api/studios/codex/sessions" in server
    assert "/api/studios/codex/sessions/{session_id}/approvals" in server


def test_material_configuration_findings_block_codex_approval(tmp_path: Path) -> None:
    transport = FakeTransport()
    manager = studio_codex.StudioCodexManager(
        transport=transport, state_root=tmp_path, repo_root=ROOT, autonomous=False
    )
    request = _proposal_request()
    request.configuration_review["requirements"][0].update(
        {
            "status": "partial",
            "proposed_correction": "Make proposal-only authority explicit in governance.",
        }
    )
    proposal = manager.create_proposal(request)

    assert proposal["readiness_gate"]["ready_for_approval"] is False
    assert proposal["readiness_gate"]["blockers"][0]["requirement_id"] == "REQ-001"
    assert "Make proposal-only authority explicit" in proposal["acceptance_criteria"][0]
    with pytest.raises(ValueError, match="resolve every configuration finding"):
        manager.approve_proposal(
            proposal["proposal_id"],
            studio_codex.CodexProposalApprovalRequest(
                actor_id="local.researcher",
                rationale="I reviewed the proposal and its remaining requirement gate.",
            ),
        )


def test_non_material_review_notes_do_not_expand_the_codex_blocker_list(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    manager = studio_codex.StudioCodexManager(
        transport=transport, state_root=tmp_path, repo_root=ROOT, autonomous=False
    )
    request = _proposal_request()
    request.configuration_review["requirements"].append(
        {
            "requirement_id": "note-copy-edit",
            "statement": "A heading could be shortened.",
            "status": "partial",
            "materiality": "low",
            "evidence": "The current heading remains valid.",
            "proposed_correction": "Consider shorter wording later.",
        }
    )

    proposal = manager.create_proposal(request)

    assert proposal["readiness_gate"]["ready_for_approval"] is True
    assert proposal["readiness_gate"]["blockers"] == []


def test_material_findings_can_be_approved_as_codex_resolution_scope(tmp_path: Path) -> None:
    transport = FakeTransport()
    manager = studio_codex.StudioCodexManager(
        transport=transport, state_root=tmp_path, repo_root=ROOT, autonomous=False
    )
    request = _proposal_request()
    request.purpose = "resolve_findings"
    request.configuration_review["requirements"][0].update(
        {
            "status": "partial",
            "proposed_correction": "Bind the intended Dashboard object through an admitted capability.",
        }
    )

    proposal = manager.create_proposal(request)

    assert proposal["purpose"] == "resolve_findings"
    assert proposal["readiness_gate"]["ready_for_approval"] is True
    assert proposal["readiness_gate"]["ready_for_admission"] is False
    assert proposal["readiness_gate"]["blockers"] == []
    assert proposal["readiness_gate"]["resolution_scope"][0]["requirement_id"] == "REQ-001"
    approved = manager.approve_proposal(
        proposal["proposal_id"],
        studio_codex.CodexProposalApprovalRequest(
            actor_id="local.researcher",
            rationale="I approve Codex to resolve this bounded configuration finding.",
        ),
    )
    session = manager.start_session(
        studio_codex.CodexSessionRequest(proposal_id=approved["proposal_id"])
    )
    assert "FINDING-RESOLUTION proposal" in transport.turns[0]["prompt"]
    assert "Dashboard object" in transport.turns[0]["prompt"]


def test_app_server_transport_pins_terra_high(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = studio_codex.CodexAppServerTransport()
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(transport, "_ensure_started", lambda: None)
    monkeypatch.setattr(
        transport,
        "_call",
        lambda method, params, **_: calls.append((method, params)) or {"thread": {"id": "thread-1"}, "turn": {"id": "turn-1"}},
    )

    transport.start_thread(cwd=ROOT)
    transport.start_turn(
        thread_id="thread-1",
        cwd=ROOT,
        prompt="Review this agent.",
        phase="planning",
        skill_path=studio_codex.AGENT_REVIEW_SKILL,
    )

    assert calls[0][1]["model"] == "gpt-5.6-terra"
    assert calls[1][1]["model"] == "gpt-5.6-terra"
    assert calls[1][1]["effort"] == "high"
    assert calls[1][1]["sandboxPolicy"]["type"] == "readOnly"
    assert calls[1][1]["input"][1]["name"] == "review-servicefabric-agent"


@pytest.mark.parametrize("action", ["turn", "review"])
def test_app_server_transport_restores_persisted_thread_after_restart(
    monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    transport = studio_codex.CodexAppServerTransport()
    calls: list[str] = []
    restored = False

    def fake_call(method: str, params: dict[str, Any], **_: Any) -> dict[str, Any]:
        nonlocal restored
        calls.append(method)
        if method == "thread/resume":
            assert params == {"threadId": "thread-persisted"}
            restored = True
            return {"thread": {"id": "thread-persisted"}}
        if not restored:
            raise RuntimeError("thread not found")
        return {"turn": {"id": "turn-restored", "status": "inProgress"}}

    monkeypatch.setattr(transport, "_ensure_started", lambda: None)
    monkeypatch.setattr(transport, "_call", fake_call)

    if action == "turn":
        result = transport.start_turn(
            thread_id="thread-persisted",
            cwd=ROOT,
            prompt="Continue the approved bounded work.",
            phase="correction",
        )
        expected_action = "turn/start"
    else:
        result = transport.review(thread_id="thread-persisted")
        expected_action = "review/start"

    assert result["turn"]["id"] == "turn-restored"
    assert calls == [expected_action, "thread/resume", expected_action]
