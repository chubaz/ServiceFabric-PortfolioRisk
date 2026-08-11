"""Development-only Studio–Codex bridge.

The browser can approve immutable Studio proposals and observe Codex work, but it
never submits shell commands, credentials, writable paths, or arbitrary runtime
configuration.  The backend compiles those values from the reviewed blueprint
and the repository's fixed development policy.
"""

from __future__ import annotations

import atexit
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, Field

from agent_studio import (
    AgentBlueprint,
    STUDIO_CODEX_MODEL,
    STUDIO_CODEX_REASONING_EFFORT,
    compile_blueprint,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def _default_state_root() -> Path:
    """Use the shared lab state repository, never a Git worktree directory."""

    for parent in (REPO_ROOT, *REPO_ROOT.parents):
        if parent.name == "worktrees":
            return parent.parent / "state" / "platform-development" / "studio-codex"
    return REPO_ROOT.parent / "state" / "platform-development" / "studio-codex"


STATE_ROOT = Path(
    os.environ.get(
        "SERVICEFABRIC_STUDIO_CODEX_ROOT",
        _default_state_root(),
    )
)
PROPOSAL_ROOT = STATE_ROOT / "proposals"
SESSION_ROOT = STATE_ROOT / "sessions"
AGENT_SKILL = REPO_ROOT / "codex" / "skills" / "build-servicefabric-agent" / "SKILL.md"
AGENT_REVIEW_SKILL = REPO_ROOT / "codex" / "skills" / "review-servicefabric-agent" / "SKILL.md"
AGENT_TEST_SKILL = REPO_ROOT / "codex" / "skills" / "test-servicefabric-agent" / "SKILL.md"
AGENT_GRAPH_SKILL = REPO_ROOT / "codex" / "skills" / "design-servicefabric-agent-graph" / "SKILL.md"
SKILL_IMPROVEMENT_SKILL = REPO_ROOT / "codex" / "skills" / "improve-servicefabric-skill" / "SKILL.md"
MAX_EVENTS = 600
MAX_DURABLE_RECORDS = 160


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


class CodexProposalRequest(BaseModel):
    blueprint: AgentBlueprint
    build_brief: str = Field(min_length=80, max_length=24_000)
    configuration_review: dict[str, Any]
    purpose: Literal["build_candidate", "resolve_findings"] = "build_candidate"


class CodexProposalApprovalRequest(BaseModel):
    actor_id: str = Field(default="local-human-reviewer", min_length=3, max_length=120)
    rationale: str = Field(min_length=10, max_length=1000)


class CodexSessionRequest(BaseModel):
    proposal_id: str = Field(min_length=8, max_length=120)


class CodexTurnRequest(BaseModel):
    phase: Literal["implementation", "correction", "skill_revision"]
    instruction: str = Field(min_length=10, max_length=6000)


class CodexApprovalRequest(BaseModel):
    request_id: str | int
    decision: Literal["accept", "acceptForSession", "decline", "cancel"]


class CodexTransport(Protocol):
    def status(self, *, probe: bool = False) -> dict[str, Any]: ...

    def start_thread(self, *, cwd: Path) -> dict[str, Any]: ...

    def start_turn(
        self,
        *,
        thread_id: str,
        cwd: Path,
        prompt: str,
        phase: str,
        skill_path: Path | None = None,
    ) -> dict[str, Any]: ...

    def review(self, *, thread_id: str) -> dict[str, Any]: ...

    def interrupt(self, *, thread_id: str, turn_id: str) -> dict[str, Any]: ...

    def respond(self, *, request_id: str | int, decision: str) -> None: ...

    def set_event_handler(self, handler: Any) -> None: ...


class CodexAppServerTransport:
    """Small synchronous JSONL client over one local Codex app-server process."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._responses: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._request_id = 0
        self._handler: Any = None
        self._initialized = False
        self._account: dict[str, Any] = {
            "checked": False,
            "authenticated": False,
            "type": None,
            "requires_openai_auth": None,
        }
        self._stderr: list[str] = []

    def set_event_handler(self, handler: Any) -> None:
        self._handler = handler

    def _version(self) -> dict[str, Any]:
        executable = shutil.which("codex")
        if not executable:
            return {"available": False, "executable": None, "version": None}
        try:
            completed = subprocess.run(
                [executable, "--version"],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            version = (completed.stdout or completed.stderr).strip().splitlines()[-1]
        except Exception:
            version = "version unavailable"
        return {"available": True, "executable": executable, "version": version}

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        version = self._version()
        if probe and version["available"]:
            try:
                self._ensure_started()
            except Exception as error:
                self._stderr.append(f"{type(error).__name__}: app-server initialization failed")
        active = self._process is not None and self._process.poll() is None
        return {
            **version,
            "process_active": active,
            "transport": "app-server-stdio-jsonl",
            "runtime_profile": {
                "model": STUDIO_CODEX_MODEL,
                "reasoning_effort": STUDIO_CODEX_REASONING_EFFORT,
                "planning": "read_only",
                "implementation": "automatic_after_job_authorization",
                "review": "automatic",
                "permission_requests": "human_approval_required",
            },
            "account": dict(self._account),
            "last_error": self._stderr[-1] if self._stderr else None,
        }

    def _ensure_started(self) -> None:
        if self._process is not None and self._process.poll() is None and self._initialized:
            return
        executable = shutil.which("codex")
        if not executable:
            raise RuntimeError("Codex CLI is not installed")
        self._process = subprocess.Popen(
            [executable, "app-server", "--stdio"],
            cwd=REPO_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._initialized = False
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._reader.start()
        self._stderr_reader.start()
        self._call(
            "initialize",
            {
                "clientInfo": {
                    "name": "servicefabric_risk_lab",
                    "title": "ServiceFabric Agent Studio",
                    "version": "0.1.0",
                }
            },
        )
        self._notify("initialized", {})
        account = self._call("account/read", {"refreshToken": False})
        account_record = account.get("account")
        requires_auth = bool(account.get("requiresOpenaiAuth", False))
        self._account = {
            "checked": True,
            "authenticated": bool(account_record) or not requires_auth,
            "type": account_record.get("type") if isinstance(account_record, dict) else None,
            "requires_openai_auth": requires_auth,
        }
        self._initialized = True

    def _read_stdout(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        for line in self._process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in message and "method" not in message:
                response_queue = self._responses.get(message["id"])
                if response_queue is not None:
                    response_queue.put(message)
                continue
            if self._handler is not None:
                self._handler(message)

    def _read_stderr(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        for line in self._process.stderr:
            cleaned = line.strip()
            if cleaned:
                self._stderr = (self._stderr + [cleaned])[-40:]

    def _send(self, message: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Codex app-server is not active")
        with self._write_lock:
            self._process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            self._process.stdin.flush()

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"method": method, "params": params})

    def _call(
        self, method: str, params: dict[str, Any], *, timeout: float = 20
    ) -> dict[str, Any]:
        with self._request_lock:
            self._request_id += 1
            request_id = self._request_id
            response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
            self._responses[request_id] = response_queue
            self._send({"method": method, "id": request_id, "params": params})
        try:
            response = response_queue.get(timeout=timeout)
        except queue.Empty as error:
            raise TimeoutError(f"Codex app-server did not answer {method}") from error
        finally:
            self._responses.pop(request_id, None)
        if response.get("error"):
            detail = response["error"].get("message", "Codex app-server request failed")
            raise RuntimeError(detail)
        return response.get("result", {})

    def start_thread(self, *, cwd: Path) -> dict[str, Any]:
        self._ensure_started()
        return self._call(
            "thread/start",
            {
                "model": STUDIO_CODEX_MODEL,
                "cwd": str(cwd),
                "approvalPolicy": "on-request",
                "sandbox": "workspace-write",
                "serviceName": "servicefabric_agent_studio",
            },
        )

    def start_turn(
        self,
        *,
        thread_id: str,
        cwd: Path,
        prompt: str,
        phase: str,
        skill_path: Path | None = None,
    ) -> dict[str, Any]:
        self._ensure_started()
        inputs: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if skill_path is not None:
            inputs.append(
                {"type": "skill", "name": skill_path.parent.name, "path": str(skill_path)}
            )
        writable = phase in {"implementation", "correction"}
        sandbox_policy: dict[str, Any] = {
            "type": "workspaceWrite" if writable else "readOnly",
            "networkAccess": False,
        }
        if writable:
            sandbox_policy["writableRoots"] = [str(cwd)]
        return self._call_with_thread_recovery(
            "turn/start",
            {
                "threadId": thread_id,
                "input": inputs,
                "cwd": str(cwd),
                "approvalPolicy": "on-request",
                "sandboxPolicy": sandbox_policy,
                "model": STUDIO_CODEX_MODEL,
                "effort": STUDIO_CODEX_REASONING_EFFORT,
                "summary": "concise",
            },
            thread_id=thread_id,
        )

    def review(self, *, thread_id: str) -> dict[str, Any]:
        self._ensure_started()
        return self._call_with_thread_recovery(
            "review/start",
            {
                "threadId": thread_id,
                "delivery": "inline",
                "target": {"type": "uncommittedChanges"},
            },
            thread_id=thread_id,
        )

    def _call_with_thread_recovery(
        self,
        method: str,
        params: dict[str, Any],
        *,
        thread_id: str,
    ) -> dict[str, Any]:
        """Retry a continued action after restoring a persisted Codex thread.

        App-server keeps active threads in process memory. Studio sessions outlive that
        process, so the first continued action after a local server restart must resume
        the recorded thread before it can start another turn or review.
        """

        try:
            return self._call(method, params)
        except RuntimeError as error:
            if "thread not found" not in str(error).lower():
                raise
        self._call("thread/resume", {"threadId": thread_id})
        return self._call(method, params)

    def interrupt(self, *, thread_id: str, turn_id: str) -> dict[str, Any]:
        self._ensure_started()
        return self._call(
            "turn/interrupt", {"threadId": thread_id, "turnId": turn_id}
        )

    def respond(self, *, request_id: str | int, decision: str) -> None:
        self._send({"id": request_id, "result": {"decision": decision}})

    def stop(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._process.kill()


class StudioCodexManager:
    """Persisted proposal and session lifecycle over a replaceable Codex transport."""

    def __init__(
        self,
        *,
        transport: CodexTransport | None = None,
        state_root: Path = STATE_ROOT,
        repo_root: Path = REPO_ROOT,
        autonomous: bool = True,
        background_dispatch: Callable[[Callable[[], None]], Any] | None = None,
    ) -> None:
        self.transport = transport or CodexAppServerTransport()
        self.state_root = state_root
        self.proposal_root = state_root / "proposals"
        self.session_root = state_root / "sessions"
        self.repo_root = repo_root.resolve()
        self.autonomous = autonomous
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="studio-codex"
        )
        self._background_dispatch = background_dispatch or self._executor.submit
        self._mutable_workspace_owner: str | None = None
        self._mutable_workspace_queue: deque[str] = deque()
        self._recovery_scheduled = False
        self.transport.set_event_handler(self._receive)

    def status(self, *, probe: bool = False) -> dict[str, Any]:
        transport = self.transport.status(probe=probe)
        git_marker = self.repo_root / ".git"
        return {
            "provider": "codex_app_server",
            "environment": "development_only",
            "transport": transport,
            "workspace": {
                "path": str(self.repo_root),
                "git_worktree": git_marker.is_file(),
                "network_access": False,
                "sandbox": "workspaceWrite",
                "approval_policy": "on-request",
            },
            "orchestration": {
                "mode": "autonomous_after_authorization" if self.autonomous else "manual",
                "worker_capacity": 4,
                "read_only_concurrency": "parallel",
                "shared_workspace_writes": "serialized",
                "pause_policy": "codex_permission_requests_only",
            },
            "boundaries": [
                "The browser submits an approved proposal id, never a shell command.",
                "Planning, implementation, verification and review advance automatically after authorization.",
                "Codex permission requests pause only the affected job; shared-worktree writes are serialized.",
                "No merge, Registry admission, worktree removal or external effect is automatic.",
            ],
        }

    def _proposal_path(self, proposal_id: str) -> Path:
        return self.proposal_root / f"{proposal_id}.json"

    def _session_path(self, session_id: str) -> Path:
        return self.session_root / f"{session_id}.json"

    def create_proposal(self, request: CodexProposalRequest) -> dict[str, Any]:
        compile_blueprint(request.blueprint, persist=False)
        blueprint = request.blueprint.model_dump(mode="json")
        review = request.configuration_review
        requirements = [
            item
            for item in review.get("requirements", [])
            if isinstance(item, dict)
        ]
        unresolved = [
            item
            for item in requirements
            if item.get("status") in {"partial", "conflict", "unproven"}
            and item.get("materiality") in {"critical", "high"}
        ]
        luna_complete = review.get("luna", {}).get("status") == "completed"
        review_matches = (
            review.get("agent_name") == request.blueprint.name
            and review.get("version") == request.blueprint.version
        )
        ready_for_codex = luna_complete and review_matches
        resolution_proposal = request.purpose == "resolve_findings"
        approval_blockers = [] if resolution_proposal else unresolved
        readiness = {
            "blueprint_valid": True,
            "configuration_review_complete": luna_complete,
            "configuration_review_matches_blueprint": review_matches,
            "requirements_passed": not unresolved,
            "ready_for_codex_resolution": ready_for_codex and bool(unresolved),
            "ready_for_admission": ready_for_codex and not unresolved,
            "ready_for_approval": ready_for_codex and not approval_blockers,
            "blockers": [
                {
                    "requirement_id": item.get("requirement_id", "requirement"),
                    "statement": item.get("statement", "Unresolved material requirement"),
                    "proposed_correction": item.get("proposed_correction", "Resolve and review again."),
                }
                for item in approval_blockers
            ],
            "resolution_scope": [
                {
                    "requirement_id": item.get("requirement_id", "requirement"),
                    "statement": item.get("statement", "Unresolved material requirement"),
                    "proposed_correction": item.get("proposed_correction", "Resolve and review again."),
                }
                for item in unresolved
            ],
        }
        compact_review = {
            "review_id": review.get("review_id"),
            "agent_name": review.get("agent_name"),
            "version": review.get("version"),
            "material_requirement_count": len(unresolved),
            "requirements": requirements,
            "object_capability_dependencies": review.get(
                "object_capability_dependencies", []
            ),
            "luna": review.get("luna", {}),
        }
        identity = _digest(
            {
                "blueprint": blueprint,
                "build_brief": request.build_brief,
                "configuration_review": compact_review,
                "purpose": request.purpose,
            }
        )
        proposal_id = f"agent-build-{identity[:16]}"
        existing = self._proposal_path(proposal_id)
        if existing.exists():
            return _load_json(existing)
        scope = request.blueprint.static_system_scope
        allowed_paths = (
            list(scope.codebase_scope)
            if scope is not None
            else [
                "packages/risk_agents",
                "apps/portfolio-risk-workbench/labs/agent_studio.py",
                "tests/application/test_agent_studio.py",
                "codex/skills/build-servicefabric-agent",
            ]
        )
        proposal = {
            "proposal_id": proposal_id,
            "kind": "AgentBlueprintCodexBuildProposal",
            "status": "draft",
            "purpose": request.purpose,
            "created_at": _now(),
            "updated_at": _now(),
            "blueprint_digest": _digest(blueprint),
            "blueprint": blueprint,
            "build_brief": request.build_brief,
            "configuration_review": compact_review,
            "readiness_gate": readiness,
            "acceptance_criteria": [
                item.get("proposed_correction") or item.get("statement")
                for item in unresolved
            ] + [
                "The reconstructed AgentBlueprint validates and compiles.",
                "Representative, failure-boundary and adversarial fixtures pass.",
                "Focused tests and diff checks pass without weakening governance.",
            ],
            "skill": {
                "id": "build-servicefabric-agent",
                "path": str(AGENT_SKILL.relative_to(REPO_ROOT)),
            },
            "supporting_skills": [
                {"id": "review-servicefabric-agent", "path": str(AGENT_REVIEW_SKILL.relative_to(REPO_ROOT))},
                {"id": "test-servicefabric-agent", "path": str(AGENT_TEST_SKILL.relative_to(REPO_ROOT))},
                {"id": "design-servicefabric-agent-graph", "path": str(AGENT_GRAPH_SKILL.relative_to(REPO_ROOT))},
            ],
            "skill_learning": {
                "enabled": True,
                "mode": "post_run_candidate_only",
                "skill": {
                    "id": "improve-servicefabric-skill",
                    "path": str(SKILL_IMPROVEMENT_SKILL.relative_to(REPO_ROOT)),
                },
                "candidate_paths": sorted(
                    {
                        str(AGENT_SKILL.parent.relative_to(REPO_ROOT)),
                        str(AGENT_REVIEW_SKILL.parent.relative_to(REPO_ROOT)),
                        str(AGENT_TEST_SKILL.parent.relative_to(REPO_ROOT)),
                        str(AGENT_GRAPH_SKILL.parent.relative_to(REPO_ROOT)),
                    }
                ),
                "activation": "separate_human_review_required",
            },
            "allowed_paths": allowed_paths,
            "forbidden_paths": [
                "vendor/servicefabric",
                "private-data",
                "licensed databases",
                "credential stores",
            ],
            "verification_commands": [
                "python3 -m pytest -q tests/application/test_agent_studio.py",
                "node --check apps/portfolio-risk-workbench/labs/labs.js",
                "git diff --check",
            ],
            "human_approval": None,
        }
        _atomic_json(existing, proposal)
        return proposal

    def approve_proposal(
        self, proposal_id: str, request: CodexProposalApprovalRequest
    ) -> dict[str, Any]:
        path = self._proposal_path(proposal_id)
        if not path.exists():
            raise KeyError(proposal_id)
        proposal = _load_json(path)
        if proposal["status"] == "approved":
            return proposal
        if proposal["status"] != "draft":
            raise ValueError(f"proposal cannot be approved from {proposal['status']}")
        gate = proposal.get("readiness_gate", {})
        if not gate.get("ready_for_approval"):
            blockers = gate.get("blockers", [])
            raise ValueError(
                "proposal is not ready: resolve every configuration finding "
                f"and run the Studio review again ({len(blockers)} blocker(s))"
            )
        proposal["status"] = "approved"
        proposal["updated_at"] = _now()
        proposal["human_approval"] = {
            "actor_id": request.actor_id,
            "rationale": request.rationale,
            "approved_at": _now(),
        }
        _atomic_json(path, proposal)
        return proposal

    def list_proposals(self) -> list[dict[str, Any]]:
        if not self.proposal_root.exists():
            return []
        return [_load_json(path) for path in sorted(self.proposal_root.glob("*.json"))]

    def start_session(self, request: CodexSessionRequest) -> dict[str, Any]:
        proposal_path = self._proposal_path(request.proposal_id)
        if not proposal_path.exists():
            raise KeyError(request.proposal_id)
        proposal = _load_json(proposal_path)
        if proposal["status"] != "approved":
            raise PermissionError("proposal requires explicit human approval")
        for session in self.list_sessions():
            if session["proposal_id"] == request.proposal_id and session["status"] != "archived":
                return session
        status = self.transport.status(probe=True)
        if not status.get("available") or not status.get("process_active"):
            raise RuntimeError(status.get("last_error") or "Codex app-server unavailable")
        account = status.get("account", {})
        if account.get("checked") and not account.get("authenticated"):
            raise PermissionError("Codex authentication is required")
        thread_result = self.transport.start_thread(cwd=self.repo_root)
        thread = thread_result.get("thread", {})
        thread_id = thread.get("id")
        if not thread_id:
            raise RuntimeError("Codex did not return a thread id")
        session_id = f"studio-codex-{_digest({'proposal': request.proposal_id, 'thread': thread_id})[:16]}"
        session = {
            "session_id": session_id,
            "proposal_id": request.proposal_id,
            "status": "planning",
            "created_at": _now(),
            "updated_at": _now(),
            "thread_id": thread_id,
            "active_turn_id": None,
            "instruction_sources": thread_result.get("instructionSources", []),
            "skill": proposal["skill"],
            "runtime_profile": {
                "model": STUDIO_CODEX_MODEL,
                "reasoning_effort": STUDIO_CODEX_REASONING_EFFORT,
                "planning": "read_only",
                "implementation": "automatic_after_job_authorization",
                "review": "automatic",
                "permission_requests": "human_approval_required",
            },
            "orchestration": {
                "mode": "autonomous_after_authorization",
                "current_stage": "planning",
                "shared_workspace_write_policy": "serialized",
            },
            "workspace": str(self.repo_root),
            "turns": [],
            "events": [],
            "pending_approvals": [],
            "latest_diff": "",
            "review": None,
            "live_activity": None,
            "documents": [],
        }
        _atomic_json(self._session_path(session_id), session)
        prompt = self._planning_prompt(proposal)
        turn_result = self.transport.start_turn(
            thread_id=thread_id,
            cwd=self.repo_root,
            prompt=prompt,
            phase="planning",
            skill_path=AGENT_REVIEW_SKILL,
        )
        turn = turn_result.get("turn", {})
        session = self.get_session(session_id)
        session["active_turn_id"] = turn.get("id")
        session["turns"].append(
            {"turn_id": turn.get("id"), "phase": "planning", "status": turn.get("status")}
        )
        session["events"].append(
            self._event("session/planning-started", {"turn": turn}, "Planning started")
        )
        _atomic_json(self._session_path(session_id), session)
        return session

    def _planning_prompt(self, proposal: dict[str, Any]) -> str:
        resolution_scope = proposal.get("readiness_gate", {}).get(
            "resolution_scope", []
        )
        resolution_instruction = (
            "This is a FINDING-RESOLUTION proposal. The unresolved findings below are the "
            "approved work scope, not reasons to refuse the task. Inspect existing system objects "
            "and admitted capabilities first; reuse or bind them where possible. When repository "
            "work is necessary, propose the smallest implementation that makes the reconstructed "
            "blueprint pass review.\n"
            if proposal.get("purpose") == "resolve_findings"
            else "This is a candidate-build proposal whose configuration gates already pass.\n"
        )
        return (
            "$review-servicefabric-agent\n$build-servicefabric-agent\n\n"
            "PLAN ONLY. Do not edit files in this turn. Inspect the repository instructions and "
            "the approved proposal below. Explain the smallest implementation that reuses canonical "
            "contracts, list exact files, tests, risks, and any blocking question.\n\n"
            f"{resolution_instruction}"
            f"Approved Studio proposal: {proposal['proposal_id']}\n"
            f"Proposal purpose: {proposal.get('purpose', 'build_candidate')}\n"
            f"Approved finding scope: {json.dumps(resolution_scope)}\n"
            f"Allowed paths: {json.dumps(proposal['allowed_paths'])}\n"
            f"Forbidden paths: {json.dumps(proposal['forbidden_paths'])}\n"
            f"Verification: {json.dumps(proposal['verification_commands'])}\n\n"
            f"Build brief:\n{proposal['build_brief']}\n\n"
            f"Approved blueprint:\n{json.dumps(proposal['blueprint'], indent=2, sort_keys=True)}"
        )

    def start_turn(self, session_id: str, request: CodexTurnRequest) -> dict[str, Any]:
        session = self.get_session(session_id)
        allowed = {
            "implementation": {"queued_implementation", "awaiting_implementation_approval", "review_complete"},
            "correction": {"awaiting_review", "review_complete"},
            "skill_revision": {"review_complete"},
        }
        if session["status"] not in allowed[request.phase]:
            raise ValueError(
                f"{request.phase} turn cannot start from {session['status']}"
            )
        mutable = request.phase in {"implementation", "correction", "skill_revision"}
        if mutable:
            with self._lock:
                if self._mutable_workspace_owner not in {None, session_id}:
                    raise RuntimeError(
                        "the shared development worktree is busy; this mutable job remains queued"
                    )
                self._mutable_workspace_owner = session_id
        proposal = _load_json(self._proposal_path(session["proposal_id"]))
        if request.phase == "skill_revision":
            learning = proposal.get("skill_learning", {})
            skill_paths = learning.get("candidate_paths") or [
                str(AGENT_SKILL.parent.relative_to(REPO_ROOT)),
                str(AGENT_REVIEW_SKILL.parent.relative_to(REPO_ROOT)),
                str(AGENT_TEST_SKILL.parent.relative_to(REPO_ROOT)),
                str(AGENT_GRAPH_SKILL.parent.relative_to(REPO_ROOT)),
            ]
            phase_instruction = (
                "$improve-servicefabric-skill\n\nUse the completed run record, final candidate "
                "diff, verification and independent review as evidence. Identify only reusable "
                "procedural gaps. Modify the smallest appropriate repository-owned skill candidate; "
                "do not activate, publish or merge it. Validate the changed skill and finish with a "
                "before/after explanation, context-cost impact and explicit review decision.\n\n"
            )
            allowed_paths = skill_paths
            skill_path = SKILL_IMPROVEMENT_SKILL
        else:
            phase_instruction = (
                "The human approved the plan. Implement the approved proposal now. "
                if request.phase == "implementation"
                else "Apply only the reviewed correction below. Preserve the approved blueprint and boundaries. "
            )
            phase_instruction = (
                f"$build-servicefabric-agent\n\n{phase_instruction}"
                "At the end, add a short `Skill feedback` section. Record only concrete, reusable "
                "gaps observed in the loaded skill; do not edit a skill during this implementation turn. "
                "Say `No reusable skill gap` when the issue was task-specific.\n\n"
            )
            allowed_paths = proposal["allowed_paths"]
            skill_path = AGENT_SKILL
        prompt = (
            phase_instruction
            + "Use apply_patch for edits, remain inside the allowed paths, run the declared verification, "
            "and finish with a concise handoff covering files changed, tests, limitations and blueprint traceability.\n\n"
            f"Human instruction: {request.instruction}\n"
            f"Allowed paths: {json.dumps(allowed_paths)}\n"
            f"Forbidden paths: {json.dumps(proposal['forbidden_paths'])}"
        )
        try:
            result = self.transport.start_turn(
                thread_id=session["thread_id"],
                cwd=self.repo_root,
                prompt=prompt,
                phase=request.phase,
                skill_path=skill_path,
            )
        except Exception:
            if mutable:
                self._release_mutable_workspace(session_id)
            raise
        turn = result.get("turn", {})
        session = self.get_session(session_id)
        session["status"] = {
            "implementation": "implementing",
            "correction": "correcting",
            "skill_revision": "improving_skill",
        }[request.phase]
        session["active_turn_id"] = turn.get("id")
        session["turns"].append(
            {"turn_id": turn.get("id"), "phase": request.phase, "status": turn.get("status")}
        )
        session["updated_at"] = _now()
        session["events"].append(
            self._event(f"session/{request.phase}-started", {"turn": turn}, f"{request.phase.title()} started")
        )
        _atomic_json(self._session_path(session_id), session)
        return session

    def _dispatch(self, task: Callable[[], None]) -> None:
        self._background_dispatch(task)

    def _record_orchestration_failure(self, session_id: str, error: Exception) -> None:
        with self._lock:
            try:
                session = self.get_session(session_id)
            except KeyError:
                return
            session["status"] = "failed"
            session["active_turn_id"] = None
            session["live_activity"] = None
            session["events"].append(
                self._event(
                    "session/orchestration-failed",
                    {"message": str(error)},
                    "Autonomous orchestration failed",
                )
            )
            session["updated_at"] = _now()
            _atomic_json(self._session_path(session_id), session)
        self._release_mutable_workspace(session_id)

    def _recover_orphaned_sessions(self) -> None:
        """Continue jobs whose app-server process ended with the web server.

        A resumed mutable turn is intentionally idempotent: Codex receives the existing
        thread history and current worktree diff, then finishes the approved bounded job.
        """

        transport_status = self.transport.status(probe=True)
        if not transport_status.get("process_active"):
            return
        for path in sorted(self.session_root.glob("*.json")):
            session = self.get_session(path.stem)
            status = session.get("status")
            if status in {
                "planning",
                "queued_implementation",
                "awaiting_implementation_approval",
                "implementing",
                "correcting",
            }:
                session["status"] = "queued_implementation"
                session["active_turn_id"] = None
                session["live_activity"] = None
                session["events"].append(
                    self._event(
                        "session/recovered",
                        {"next_stage": "implementation"},
                        "Autonomous job recovered after restart",
                    )
                )
                session["updated_at"] = _now()
                _atomic_json(path, session)
                self._queue_automatic_implementation(session["session_id"])
            elif status in {"awaiting_review", "reviewing", "awaiting_skill_review"}:
                session["status"] = "awaiting_review"
                session["active_turn_id"] = None
                session["live_activity"] = None
                session["events"].append(
                    self._event(
                        "session/recovered",
                        {"next_stage": "review"},
                        "Autonomous review recovered after restart",
                    )
                )
                session["updated_at"] = _now()
                _atomic_json(path, session)
                self._dispatch(
                    lambda session_id=session["session_id"]: self._start_automatic_review(
                        session_id
                    )
                )

    def schedule_recovery(self) -> None:
        """Resume persisted active jobs once when the Studio UI reconnects."""

        if not self.autonomous or not self.session_root.exists():
            return
        active_statuses = {
            "planning",
            "queued_implementation",
            "awaiting_implementation_approval",
            "implementing",
            "correcting",
            "awaiting_review",
            "reviewing",
            "awaiting_skill_review",
        }
        with self._lock:
            if self._recovery_scheduled:
                return
            has_active = any(
                _load_json(path).get("status") in active_statuses
                for path in self.session_root.glob("*.json")
            )
            if not has_active:
                return
            self._recovery_scheduled = True
        self._dispatch(self._recover_orphaned_sessions)

    def _start_automatic_implementation(self, session_id: str) -> None:
        try:
            self.start_turn(
                session_id,
                CodexTurnRequest(
                    phase="implementation",
                    instruction=(
                        "Implement the approved plan, run the declared verification, and continue "
                        "to independent review. Pause only when the Codex permission protocol "
                        "requires a human decision."
                    ),
                ),
            )
        except Exception as error:
            self._record_orchestration_failure(session_id, error)

    def _start_automatic_review(self, session_id: str) -> None:
        try:
            self.review(session_id)
        except Exception as error:
            self._record_orchestration_failure(session_id, error)

    def _queue_automatic_implementation(self, session_id: str) -> None:
        with self._lock:
            if self._mutable_workspace_owner in {None, session_id}:
                self._mutable_workspace_owner = session_id
                should_start = True
            else:
                if session_id not in self._mutable_workspace_queue:
                    self._mutable_workspace_queue.append(session_id)
                should_start = False
        if should_start:
            self._dispatch(lambda: self._start_automatic_implementation(session_id))

    def _release_mutable_workspace(self, session_id: str) -> None:
        next_session: str | None = None
        with self._lock:
            if self._mutable_workspace_owner == session_id:
                self._mutable_workspace_owner = None
            while self._mutable_workspace_owner is None and self._mutable_workspace_queue:
                candidate = self._mutable_workspace_queue.popleft()
                try:
                    candidate_session = self.get_session(candidate)
                except KeyError:
                    continue
                if candidate_session.get("status") != "queued_implementation":
                    continue
                self._mutable_workspace_owner = candidate
                next_session = candidate
                break
        if next_session:
            self._dispatch(lambda: self._start_automatic_implementation(next_session))

    def review(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session["status"] not in {
            "awaiting_review",
            "awaiting_skill_review",
            "review_complete",
        }:
            raise ValueError(f"review cannot start from {session['status']}")
        result = self.transport.review(thread_id=session["thread_id"])
        turn = result.get("turn", {})
        session = self.get_session(session_id)
        session["status"] = "reviewing"
        session["active_turn_id"] = turn.get("id")
        session["turns"].append(
            {"turn_id": turn.get("id"), "phase": "review", "status": turn.get("status")}
        )
        session["events"].append(
            self._event("session/review-started", {"turn": turn}, "Independent review started")
        )
        session["updated_at"] = _now()
        _atomic_json(self._session_path(session_id), session)
        return session

    def interrupt(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if not session.get("active_turn_id"):
            raise ValueError("session has no active turn")
        self.transport.interrupt(
            thread_id=session["thread_id"], turn_id=session["active_turn_id"]
        )
        session["events"].append(
            self._event("session/interrupt-requested", {}, "Interrupt requested by human")
        )
        session["updated_at"] = _now()
        _atomic_json(self._session_path(session_id), session)
        return session

    def respond_approval(
        self, session_id: str, request: CodexApprovalRequest
    ) -> dict[str, Any]:
        session = self.get_session(session_id)
        pending = next(
            (
                item
                for item in session["pending_approvals"]
                if str(item["request_id"]) == str(request.request_id)
            ),
            None,
        )
        if pending is None:
            raise KeyError(str(request.request_id))
        self.transport.respond(request_id=pending["request_id"], decision=request.decision)
        pending["decision"] = request.decision
        pending["resolved_at"] = _now()
        session["pending_approvals"] = [
            item for item in session["pending_approvals"] if item is not pending
        ]
        session["events"].append(
            self._event(
                "session/approval-resolved",
                {"method": pending["method"], "decision": request.decision},
                f"Human chose {request.decision}",
            )
        )
        session["updated_at"] = _now()
        _atomic_json(self._session_path(session_id), session)
        return session

    def get_session(self, session_id: str) -> dict[str, Any]:
        path = self._session_path(session_id)
        if not path.exists():
            raise KeyError(session_id)
        session = _load_json(path)
        original = json.dumps(session, sort_keys=True)
        session["events"] = [
            event
            for event in session.get("events", [])
            if self._event_is_durable(
                event.get("method", ""), event.get("payload", {})
            )
        ][-MAX_DURABLE_RECORDS:]
        session.setdefault("documents", [])
        session.setdefault("live_activity", None)
        if session.get("status") not in {
            "planning",
            "implementing",
            "correcting",
            "reviewing",
            "improving_skill",
        }:
            session["live_activity"] = None
        final_diff = session.get("latest_diff", "")
        if final_diff and not any(
            item.get("kind") == "candidate_diff"
            and item.get("digest") == _digest(final_diff)
            for item in session["documents"]
        ):
            digest = _digest(final_diff)
            latest_phase = next(
                (
                    item.get("phase")
                    for item in reversed(session.get("turns", []))
                    if item.get("status") in {"completed", "failed", "interrupted"}
                ),
                "implementation",
            )
            session["documents"].append(
                {
                    "document_id": f"doc-{digest[:16]}",
                    "kind": "candidate_diff",
                    "phase": latest_phase,
                    "title": f"{str(latest_phase).replace('_', ' ').title()} candidate diff",
                    "created_at": session.get("updated_at", _now()),
                    "digest": digest,
                    "content": final_diff,
                }
            )
        if json.dumps(session, sort_keys=True) != original:
            _atomic_json(path, session)
        return session

    def list_sessions(self) -> list[dict[str, Any]]:
        if not self.session_root.exists():
            return []
        sessions = [
            self.get_session(path.stem) for path in self.session_root.glob("*.json")
        ]
        return sorted(sessions, key=lambda item: item["updated_at"], reverse=True)

    def archive(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session["status"] in {
            "planning",
            "queued_implementation",
            "implementing",
            "correcting",
            "awaiting_review",
            "reviewing",
        }:
            raise ValueError("interrupt the active turn before archiving")
        session["status"] = "archived"
        session["archived_at"] = _now()
        session["updated_at"] = _now()
        _atomic_json(self._session_path(session_id), session)
        return session

    def _event(self, method: str, payload: dict[str, Any], label: str) -> dict[str, Any]:
        return {
            "event_id": f"evt-{_digest({'method': method, 'payload': payload, 'at': time.time_ns()})[:16]}",
            "method": method,
            "label": label,
            "occurred_at": _now(),
            "payload": payload,
        }

    def _receive(self, message: dict[str, Any]) -> None:
        params = message.get("params") or {}
        thread_id = params.get("threadId")
        if not thread_id and isinstance(params.get("thread"), dict):
            thread_id = params["thread"].get("id")
        if not thread_id:
            return
        with self._lock:
            session = next(
                (item for item in self.list_sessions() if item.get("thread_id") == thread_id),
                None,
            )
            if session is None:
                return
            method = message.get("method", "unknown")
            label = self._label(method, params)
            retained_params = self._sanitized_event_params(method, params)
            session["events"] = [
                event
                for event in session.get("events", [])
                if self._event_is_durable(
                    event.get("method", ""), event.get("payload", {})
                )
            ][-MAX_DURABLE_RECORDS:]
            if self._event_is_durable(method, retained_params):
                session["events"] = (
                    session["events"]
                    + [self._event(method, retained_params, label)]
                )[-MAX_DURABLE_RECORDS:]
            else:
                session["live_activity"] = {
                    "label": label,
                    "phase": next(
                        (
                            item.get("phase")
                            for item in reversed(session.get("turns", []))
                            if item.get("turn_id") == session.get("active_turn_id")
                        ),
                        None,
                    ),
                    "updated_at": _now(),
                }
            if "id" in message and method.endswith("requestApproval"):
                session["pending_approvals"].append(
                    {
                        "request_id": message["id"],
                        "method": method,
                        "reason": params.get("reason"),
                        "command": params.get("command"),
                        "cwd": params.get("cwd"),
                        "item_id": params.get("itemId"),
                        "requested_at": _now(),
                    }
                )
            if method == "turn/diff/updated":
                session["latest_diff"] = params.get("diff", "")
            if method == "item/completed":
                item = params.get("item") or {}
                if item.get("type") == "exitedReviewMode":
                    session["review"] = item.get("review")
            if method == "turn/completed":
                turn = params.get("turn") or {}
                turn_id = turn.get("id")
                phase = next(
                    (
                        item["phase"]
                        for item in reversed(session["turns"])
                        if item.get("turn_id") == turn_id
                    ),
                    None,
                )
                for item in session["turns"]:
                    if item.get("turn_id") == turn_id:
                        item["status"] = turn.get("status")
                session["active_turn_id"] = None
                session["live_activity"] = None
                final_diff = session.get("latest_diff", "")
                if final_diff:
                    documents = session.setdefault("documents", [])
                    digest = _digest(final_diff)
                    if not any(
                        item.get("kind") == "candidate_diff"
                        and item.get("digest") == digest
                        for item in documents
                    ):
                        documents.append(
                            {
                                "document_id": f"doc-{digest[:16]}",
                                "kind": "candidate_diff",
                                "phase": phase,
                                "title": f"{str(phase or 'turn').replace('_', ' ').title()} candidate diff",
                                "created_at": _now(),
                                "digest": digest,
                                "content": final_diff,
                            }
                        )
                if turn.get("status") == "failed":
                    session["status"] = "failed"
                elif turn.get("status") == "interrupted":
                    session["status"] = "interrupted"
                elif phase == "planning":
                    session["status"] = (
                        "queued_implementation"
                        if self.autonomous
                        else "awaiting_implementation_approval"
                    )
                elif phase in {"implementation", "correction"}:
                    session["status"] = "awaiting_review"
                elif phase == "skill_revision":
                    session["status"] = "awaiting_skill_review"
                elif phase == "review":
                    session["status"] = "review_complete"
            session["updated_at"] = _now()
            _atomic_json(self._session_path(session["session_id"]), session)
            if method == "turn/completed" and turn.get("status") == "completed":
                if phase == "planning" and self.autonomous:
                    self._queue_automatic_implementation(session["session_id"])
                elif phase in {"implementation", "correction"} and self.autonomous:
                    self._release_mutable_workspace(session["session_id"])
                    self._dispatch(
                        lambda: self._start_automatic_review(session["session_id"])
                    )
                elif phase == "skill_revision":
                    self._release_mutable_workspace(session["session_id"])

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _sanitized_event_params(method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Retain useful work receipts without private reasoning content."""

        retained = json.loads(json.dumps(params))
        item = retained.get("item")
        if isinstance(item, dict) and item.get("type") == "reasoning":
            item.pop("content", None)
        if method == "item/reasoning/textDelta":
            retained.pop("delta", None)
            retained["disclosure"] = "private reasoning content not retained"
        return retained

    @staticmethod
    def _event_is_durable(method: str, params: dict[str, Any]) -> bool:
        """Persist work products and decisions, not streaming transport noise."""

        if method.startswith("session/"):
            return True
        if method in {
            "turn/started",
            "turn/completed",
            "turn/plan/updated",
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "error",
        }:
            return True
        if method != "item/completed":
            return False
        item_type = (params.get("item") or {}).get("type")
        return item_type in {
            "agentMessage",
            "commandExecution",
            "fileChange",
            "exitedReviewMode",
            "mcpToolCall",
            "webSearch",
        }

    @staticmethod
    def _label(method: str, params: dict[str, Any]) -> str:
        item = params.get("item") or {}
        labels = {
            "turn/started": "Codex turn started",
            "turn/completed": "Codex turn completed",
            "turn/plan/updated": "Implementation plan updated",
            "turn/diff/updated": "Candidate diff updated",
            "item/commandExecution/requestApproval": "Command needs human approval",
            "item/fileChange/requestApproval": "File change needs human approval",
            "error": "Codex reported an error",
        }
        if method in {"item/started", "item/completed"} and item.get("type"):
            return f"{item['type'].replace('_', ' ').title()} {method.split('/')[-1]}"
        return labels.get(method, method.replace("/", " · ").replace("_", " ").title())


studio_codex_manager = StudioCodexManager()


def _stop_transport() -> None:
    studio_codex_manager.shutdown()
    stop = getattr(studio_codex_manager.transport, "stop", None)
    if callable(stop):
        stop()


atexit.register(_stop_transport)
