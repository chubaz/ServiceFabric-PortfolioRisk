"""Deterministic synthetic intraday runtime for the local Workflow Cycle Console."""

from __future__ import annotations

import hashlib
import math
import random
import tempfile
import threading
import time
from collections import deque
from datetime import date, datetime, time as wall_time, timedelta, timezone
from pathlib import Path
from typing import Any

from risk_decisions import (
    DecisionOutcome,
    DecisionProposal,
    DecisionState,
    LocalDecisionStore,
    admit_proposal,
    canonical_digest,
    resolve,
)
from decision_review import decision_store


MARKET_OPEN = wall_time(9, 30)
SECONDS_PER_DAY = 6 * 60 * 60 + 30 * 60
MAX_CANDLES = 1_200


def _iso_at(day: date, seconds: int) -> str:
    value = datetime.combine(day, MARKET_OPEN, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )
    return value.isoformat()


def _pct(value: float) -> str:
    return f"{value:.2%}"


class SyntheticWorkflowSession:
    """One replay session with sealed real closes and released synthetic ticks."""

    def __init__(self, session_id: str, configuration: dict[str, Any], *, decision_store: LocalDecisionStore | None = None) -> None:
        self.session_id = session_id
        self.configuration = configuration
        self.lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.running = False
        self.status = "ready"
        self.speed = float(configuration.get("speed", 60))
        self.seed = int(configuration.get("seed", 20260802))
        self.rng = random.Random(self.seed)
        self.day_index = 0
        self.second = 0
        self.accumulator = 0.0
        self.current_prices: dict[str, float] = {}
        self.previous_prices: dict[str, float] = {}
        self.current_nav = 0.0
        self.open_nav = 0.0
        self.prior_close_nav: float | None = None
        self.current_candles: dict[str, dict[str, Any]] = {}
        self.candles: dict[str, deque[dict[str, Any]]] = {
            instrument["instrument_id"]: deque(maxlen=MAX_CANDLES)
            for instrument in configuration["instruments"]
        }
        self.candles["portfolio"] = deque(maxlen=MAX_CANDLES)
        self.events: deque[dict[str, Any]] = deque(maxlen=300)
        self.findings: list[dict[str, Any]] = []
        self.decision_proposals: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.consequence_receipts: list[dict[str, Any]] = []
        self.context_revisions: list[dict[str, Any]] = []
        self.follow_up_runs: list[dict[str, Any]] = []
        self._temporary_decision_root = None
        if decision_store is None:
            self._temporary_decision_root = tempfile.TemporaryDirectory(
                prefix="portfolio-risk-decisions-", dir=Path(tempfile.gettempdir()).resolve()
            )
            decision_store = LocalDecisionStore(self._temporary_decision_root.name)
        self.decision_store = decision_store
        self.daily_history: list[dict[str, Any]] = []
        self.dashboard_version = 1
        self.dashboard_pages = [
            {
                "page_id": "overview",
                "title": "Portfolio overview",
                "purpose": "Current simulated portfolio state and material movement.",
                "agent_id": "daily-portfolio-risk-reviewer",
            },
            {
                "page_id": "market",
                "title": "Simulated market tape",
                "purpose": "Synthetic one-minute candles and position-level movement.",
                "agent_id": "market-liquidity-risk-analyst",
            },
            {
                "page_id": "risk",
                "title": "Risk and review",
                "purpose": "Threshold findings, decision proposals and human resolutions.",
                "agent_id": "concentration-mandate-monitor",
            },
            {
                "page_id": "agents",
                "title": "Latched agents",
                "purpose": "Specialists responsible for interpreting dashboard components.",
                "agent_id": None,
            },
        ]
        self.dashboard_patches: list[dict[str, Any]] = []
        self.report = self._empty_report()
        self._proposal_days: set[str] = set()
        self._start_day(0)
        self._record_event(
            "runtime",
            "Session prepared",
            "Real daily closes are sealed; only released synthetic observations are visible to workflows.",
        )
        self._patch_dashboard(
            "initialize",
            "overview",
            "Created the four-page live monitoring package for this session.",
        )

    @property
    def intervals(self) -> list[dict[str, Any]]:
        return self.configuration["intervals"]

    @property
    def instruments(self) -> list[dict[str, Any]]:
        return self.configuration["instruments"]

    def _empty_report(self) -> dict[str, Any]:
        return {
            "title": "Simulated portfolio risk review",
            "as_of": None,
            "status": "Waiting for synthetic observations",
            "sections": [
                {
                    "section_id": "executive_signal",
                    "title": "Executive signal",
                    "content": "The workflow cycle has not started.",
                },
                {
                    "section_id": "what_changed",
                    "title": "What changed",
                    "items": [],
                },
                {
                    "section_id": "risk_interpretation",
                    "title": "Risk interpretation",
                    "content": "No intraday risk observation is available yet.",
                },
                {
                    "section_id": "exposure_mandate",
                    "title": "Exposure and mandate",
                    "content": "Awaiting current portfolio valuation.",
                },
                {
                    "section_id": "uncertainty",
                    "title": "Uncertainty",
                    "items": [
                        "Every intraday observation is synthetic and is not empirical market evidence."
                    ],
                },
                {
                    "section_id": "review_actions",
                    "title": "Review actions",
                    "items": ["Start the workflow cycle."],
                },
            ],
        }

    def _record_event(self, kind: str, title: str, detail: str) -> None:
        self.events.appendleft(
            {
                "timestamp": _iso_at(self.current_day, self.second),
                "kind": kind,
                "title": title,
                "detail": detail,
            }
        )

    def _patch_dashboard(self, action: str, page_id: str, rationale: str) -> None:
        self.dashboard_version += 1
        self.dashboard_patches.append(
            {
                "patch_id": f"patch-{self.dashboard_version:04d}",
                "version": self.dashboard_version,
                "action": action,
                "page_id": page_id,
                "rationale": rationale,
                "as_of": _iso_at(self.current_day, self.second),
                "capability_id": "meta.dashboard.patch",
                "effects": ["write_run_artifact"],
            }
        )
        self.dashboard_patches = self.dashboard_patches[-100:]

    @property
    def current_day(self) -> date:
        return date.fromisoformat(self.intervals[self.day_index]["date"])

    def _start_day(self, index: int) -> None:
        self.day_index = index
        self.second = 0
        interval = self.intervals[index]
        self.current_prices = {
            key: float(value) for key, value in interval["open_prices"].items()
        }
        self.previous_prices = dict(self.current_prices)
        self.current_candles = {}
        self.current_nav = self._portfolio_nav(self.current_prices)
        self.open_nav = self.current_nav
        if self.prior_close_nav is None:
            self.prior_close_nav = self.open_nav
        self.report = self._build_report(intraday=True)

    def _portfolio_nav(self, prices: dict[str, float]) -> float:
        quantities = self.configuration["quantities"]
        return float(self.configuration["cash"]) + sum(
            float(quantities[instrument_id]) * price
            for instrument_id, price in prices.items()
        )

    def _update_candle(self, instrument_id: str, value: float) -> None:
        minute = self.second // 60
        candle = self.current_candles.get(instrument_id)
        if candle is None or candle["minute"] != minute:
            if candle is not None:
                self.candles[instrument_id].append(dict(candle))
            candle = {
                "minute": minute,
                "timestamp": _iso_at(self.current_day, minute * 60),
                "open": value,
                "high": value,
                "low": value,
                "close": value,
                "updates": 1,
                "synthetic": True,
            }
            self.current_candles[instrument_id] = candle
            return
        candle["high"] = max(candle["high"], value)
        candle["low"] = min(candle["low"], value)
        candle["close"] = value
        candle["updates"] += 1

    def _advance_second(self) -> None:
        interval = self.intervals[self.day_index]
        remaining = SECONDS_PER_DAY - self.second
        self.previous_prices = dict(self.current_prices)
        for instrument in self.instruments:
            instrument_id = instrument["instrument_id"]
            current = max(self.current_prices[instrument_id], 1e-9)
            target = max(float(interval["close_prices"][instrument_id]), 1e-9)
            if remaining <= 1:
                updated = target
            else:
                current_log = math.log(current)
                target_log = math.log(target)
                per_second_sigma = float(
                    interval["daily_volatility"].get(instrument_id, 0.02)
                ) / math.sqrt(SECONDS_PER_DAY)
                conditional_mean = current_log + (target_log - current_log) / remaining
                conditional_sigma = per_second_sigma * math.sqrt(
                    (remaining - 1) / remaining
                )
                updated = math.exp(
                    conditional_mean + conditional_sigma * self.rng.gauss(0, 1)
                )
            self.current_prices[instrument_id] = updated
            self._update_candle(instrument_id, updated)
        self.current_nav = self._portfolio_nav(self.current_prices)
        self._update_candle("portfolio", self.current_nav)
        self.second += 1
        if self.second % 60 == 0:
            self.report = self._build_report(intraday=True)
            self._evaluate_review_proposal()
        if self.second >= SECONDS_PER_DAY:
            self._complete_day()

    def _weights(self) -> list[dict[str, Any]]:
        quantities = self.configuration["quantities"]
        values = []
        for instrument in self.instruments:
            instrument_id = instrument["instrument_id"]
            market_value = float(quantities[instrument_id]) * self.current_prices[instrument_id]
            values.append(
                {
                    **instrument,
                    "price": self.current_prices[instrument_id],
                    "market_value": market_value,
                    "weight": market_value / self.current_nav if self.current_nav else 0,
                    "return_from_open": (
                        self.current_prices[instrument_id]
                        / float(self.intervals[self.day_index]["open_prices"][instrument_id])
                        - 1
                    ),
                }
            )
        return sorted(values, key=lambda item: item["weight"], reverse=True)

    def _evaluate_review_proposal(self) -> None:
        day = self.current_day.isoformat()
        intraday_return = self.current_nav / self.open_nav - 1 if self.open_nav else 0
        threshold = float(self.configuration.get("daily_loss_limit", 0.02))
        if intraday_return > -threshold or day in self._proposal_days:
            return
        self._proposal_days.add(day)
        observed_at = _iso_at(self.current_day, self.second)
        finding = {
            "finding_id": f"finding-intraday-loss-{day}",
            "artifact_type": "finding",
            "observed_at": observed_at,
            "kind": "intraday_loss_threshold",
            "summary": (
                f"The synthetic portfolio has fallen {_pct(abs(intraday_return))} "
                f"from the session open, beyond the {_pct(threshold)} review threshold."
            ),
            "evidence": {
                "intraday_return": round(intraday_return, 8),
                "review_threshold": -threshold,
                "data_origin": "simulated_seeded_intraday",
            },
            "effects": [],
        }
        created_at = datetime.now(timezone.utc)
        finding_digest = canonical_digest(finding)
        proposal_model = DecisionProposal(
            proposal_id=f"proposal-{self.session_id}-{day}-{len(self.decision_proposals) + 1}",
            finding_id=finding["finding_id"], finding_digest=finding_digest,
            question="How should the human reviewer resolve this material synthetic intraday-loss finding?",
            why_now=finding["summary"],
            proposing_agent_id="risk.agent.daily-portfolio-risk-reviewer",
            proposing_workflow_id="risk.workflow.synthetic-cycle-review",
            recommendation=DecisionOutcome.INVESTIGATE,
            mandate_relevance=f"The configured policy requires human review when the daily loss exceeds {_pct(threshold)}.",
            portfolio_relevance="The finding measures movement in total simulated portfolio NAV from the session open.",
            risk_environment_relevance="This synthetic intraday path contains no independent macro, meso, or issuer evidence.",
            evidence_ids=(finding["finding_id"],),
            capability_receipt_ids=(f"capability.synthetic-nav.{self.session_id}.{day}",),
            uncertainties=("The intraday path is a seeded workflow fixture, not empirical market evidence.",),
            missing_information=("Confirm whether the movement remains material at the next released observation.",),
            as_of=datetime.fromisoformat(observed_at), available_at=datetime.fromisoformat(observed_at),
            created_at=created_at, expires_at=created_at + timedelta(hours=4),
            downstream_workflow_preview="Investigate runs one registered effect-free evidence review. Accept or reject permits only a separate manual clock resume.",
        )
        record = self.decision_store.create(admit_proposal(proposal_model))
        proposal = proposal_model.model_dump(mode="json")
        proposal.update({"artifact_type": "decision_proposal", "status": record.state.value, "kind": "intraday_loss_review", "record_revision": record.record_revision})
        self.findings.append(finding)
        self.decision_proposals.append(proposal)
        self.running = False
        self.status = "paused_for_review"
        self._record_event(
            "decision_proposal",
            "Decision proposal requires human resolution",
            finding["summary"],
        )
        self._patch_dashboard(
            "update",
            "risk",
            "Elevated the intraday-loss finding as a decision proposal on the Risk and review page.",
        )

    def _complete_day(self) -> None:
        for instrument_id, candle in list(self.current_candles.items()):
            self.candles[instrument_id].append(dict(candle))
        close_return = self.current_nav / self.open_nav - 1 if self.open_nav else 0
        self.daily_history.append(
            {
                "date": self.current_day.isoformat(),
                "open_nav": self.open_nav,
                "close_nav": self.current_nav,
                "return": close_return,
                "synthetic_intraday": True,
                "real_close_anchor": True,
            }
        )
        self.report = self._build_report(intraday=False)
        self.prior_close_nav = self.current_nav
        self._record_event(
            "cycle",
            "Daily workflow cycle completed",
            f"The dashboard closed at {_pct(close_return)} for the synthetic intraday path.",
        )
        self._patch_dashboard(
            "carry_forward",
            "overview",
            "Carried the accepted dashboard pages and agent latches into the next workflow date.",
        )
        if self.day_index + 1 >= len(self.intervals):
            self.running = False
            self.status = "complete"
            return
        self._start_day(self.day_index + 1)

    def _build_report(self, *, intraday: bool) -> dict[str, Any]:
        weights = self._weights()
        largest = weights[0] if weights else None
        portfolio_return = self.current_nav / self.open_nav - 1 if self.open_nav else 0
        direction = "higher" if portfolio_return >= 0 else "lower"
        largest_name = largest["display_name"] if largest else "No valued holding"
        largest_weight = largest["weight"] if largest else 0
        status = (
            "Review required"
            if self.status == "paused_for_review"
            else "Intraday monitoring"
            if intraday
            else "Daily close completed"
        )
        return {
            "title": "Simulated portfolio risk review",
            "as_of": _iso_at(self.current_day, self.second),
            "status": status,
            "sections": [
                {
                    "section_id": "executive_signal",
                    "title": "Executive signal",
                    "content": (
                        f"The synthetic portfolio is {_pct(abs(portfolio_return))} {direction} "
                        f"from the session open. {largest_name} is the largest valued exposure "
                        f"at {_pct(largest_weight)}."
                    ),
                },
                {
                    "section_id": "what_changed",
                    "title": "What changed",
                    "items": [
                        f"Portfolio NAV moved from {self.open_nav:,.0f} to {self.current_nav:,.0f}.",
                        f"The stream has released {self.second:,} synthetic second observations per active position.",
                    ],
                },
                {
                    "section_id": "risk_interpretation",
                    "title": "Risk interpretation",
                    "content": (
                        "The movement remains below the configured loss-review threshold."
                        if portfolio_return > -float(self.configuration.get("daily_loss_limit", 0.02))
                        else "The loss threshold has been crossed and the workflow is paused for review."
                    ),
                },
                {
                    "section_id": "exposure_mandate",
                    "title": "Exposure and mandate",
                    "content": (
                        f"{largest_name} contributes the greatest concentration. Its current "
                        f"weight is {_pct(largest_weight)}; compare this with the approved mandate."
                    ),
                },
                {
                    "section_id": "uncertainty",
                    "title": "Uncertainty",
                    "items": [
                        "Intraday prices are a seeded Brownian bridge between real daily closes.",
                        "They demonstrate workflow behaviour and cannot support empirical intraday conclusions.",
                    ],
                },
                {
                    "section_id": "review_actions",
                    "title": "Review actions",
                    "items": [
                        "Review the largest exposure if concentration remains material.",
                        "Resume the clock only after every pending decision proposal is resolved.",
                    ],
                },
            ],
        }

    def _loop(self) -> None:
        previous = time.monotonic()
        while not self._stop_event.is_set():
            now = time.monotonic()
            elapsed = max(0.0, now - previous)
            previous = now
            with self.lock:
                if self.running and self.status not in {"complete", "paused_for_review"}:
                    self.accumulator += elapsed * self.speed
                    steps = min(int(self.accumulator), 20_000)
                    self.accumulator -= steps
                    for _ in range(steps):
                        if not self.running or self.status in {"complete", "paused_for_review"}:
                            break
                        self._advance_second()
            self._stop_event.wait(0.05)

    def ensure_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._loop,
            name=f"workflow-cycle-{self.session_id}",
            daemon=True,
        )
        self._thread.start()

    def start(self) -> None:
        with self.lock:
            if self.status == "complete":
                return
            blocked = any(
                self.decision_store.get(item["proposal_id"]).state
                not in {DecisionState.RESOLVED, DecisionState.REJECTED}
                for item in self.decision_proposals
            )
            if blocked:
                self.running = False
                self.status = "paused_for_review"
                return
            self.status = "running"
            self.running = True
            self._record_event(
                "clock",
                "Workflow cycle running",
                f"The simulation is advancing at {self.speed:g}× wall-clock speed.",
            )
        self.ensure_thread()

    def pause(self) -> None:
        with self.lock:
            self.running = False
            if self.status not in {"complete", "paused_for_review"}:
                self.status = "paused"
            self._record_event("clock", "Workflow cycle paused", "Synthetic generation stopped.")

    def set_speed(self, speed: float) -> None:
        if speed < 1 or speed > 3600:
            raise ValueError("speed must be between 1× and 3600×")
        with self.lock:
            self.speed = speed
            self._record_event(
                "clock",
                "Clock speed changed",
                f"Generation now advances {speed:g} simulated seconds per wall-clock second.",
            )

    def resolve_proposal(
        self,
        proposal_id: str,
        outcome: str,
        *,
        resolver_id: str,
        resolver_type: str,
        rationale: str,
        idempotency_key: str,
        expected_revision: str,
    ) -> None:
        with self.lock:
            proposal = next(
                (
                    item
                    for item in self.decision_proposals
                    if item["proposal_id"] == proposal_id
                ),
                None,
            )
            if not proposal:
                raise KeyError(proposal_id)
            if resolver_type != "human":
                raise ValueError("Phase 5 permits human resolvers only")
            record = resolve(
                self.decision_store, proposal_id, DecisionOutcome(outcome),
                resolver_id=resolver_id, rationale=rationale,
                idempotency_key=idempotency_key, expected_revision=expected_revision,
            )
            self._sync_decision_record(record)
            self.status = "paused_for_review" if record.state not in {DecisionState.RESOLVED, DecisionState.REJECTED} else "paused"
            decision = self.decisions[-1]
            receipt = self.consequence_receipts[-1]
            self._record_event(
                "review",
                "Human decision recorded",
                f"{decision['decision_id']} resolved {proposal_id} as {outcome}. {receipt['consequence']}",
            )

    def _sync_decision_record(self, record) -> None:  # type: ignore[no-untyped-def]
        proposal = record.proposal.model_dump(mode="json")
        proposal.update({"artifact_type": "decision_proposal", "status": record.state.value, "record_revision": record.record_revision, "kind": "intraday_loss_review"})
        self.decision_proposals = [item for item in self.decision_proposals if item["proposal_id"] != record.proposal.proposal_id]
        self.decision_proposals.append(proposal)
        self.decisions = [item for item in self.decisions if item["proposal_id"] != record.proposal.proposal_id]
        for item in record.resolutions:
            value = item.model_dump(mode="json")
            value.update({"artifact_type": "decision", "finding_id": record.proposal.finding_id, "resolver": {"resolver_id": item.resolver_id, "resolver_type": item.resolver_type}, "authority": "human_review"})
            self.decisions.append(value)
        self.consequence_receipts = [item for item in self.consequence_receipts if item["proposal_id"] != record.proposal.proposal_id]
        for item in record.consequences:
            value = item.model_dump(mode="json")
            value["artifact_type"] = "decision_consequence_receipt"
            self.consequence_receipts.append(value)
        self.context_revisions = [item for item in self.context_revisions if item["proposal_id"] != record.proposal.proposal_id]
        self.context_revisions.extend(item.model_dump(mode="json") for item in record.context_revisions)
        self.follow_up_runs = [item for item in self.follow_up_runs if item["proposal_id"] != record.proposal.proposal_id]
        self.follow_up_runs.extend(item.model_dump(mode="json") for item in record.follow_up_runs)

    def attach_agent(self, page_id: str, agent_id: str) -> None:
        with self.lock:
            page = next(
                (item for item in self.dashboard_pages if item["page_id"] == page_id),
                None,
            )
            if not page:
                raise KeyError(page_id)
            page["agent_id"] = agent_id
            self._patch_dashboard(
                "attach_agent",
                page_id,
                f"Attached the reviewed {agent_id} specialist to this dashboard page.",
            )

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            visible_candles: dict[str, list[dict[str, Any]]] = {}
            for instrument_id, values in self.candles.items():
                combined = list(values)
                current = self.current_candles.get(instrument_id)
                if current is not None:
                    combined.append(dict(current))
                visible_candles[instrument_id] = combined[-180:]
            weights = self._weights()
            return {
                "session_id": self.session_id,
                "status": self.status,
                "running": self.running,
                "speed": self.speed,
                "seed": self.seed,
                "portfolio_id": self.configuration["portfolio_id"],
                "portfolio_name": self.configuration["portfolio_name"],
                "data_truth": {
                    "daily_anchors": "real CRSP closes",
                    "intraday": "synthetic seeded Brownian bridge",
                    "empirical_intraday": False,
                    "look_ahead_rule": "future close anchors remain sealed from agent context until released by the clock",
                },
                "clock": {
                    "date": self.current_day.isoformat(),
                    "timestamp": _iso_at(self.current_day, self.second),
                    "second_of_session": self.second,
                    "seconds_per_day": SECONDS_PER_DAY,
                    "day_index": self.day_index,
                    "day_count": len(self.intervals),
                },
                "market": {
                    "nav": self.current_nav,
                    "open_nav": self.open_nav,
                    "return_from_open": self.current_nav / self.open_nav - 1
                    if self.open_nav
                    else 0,
                    "positions": weights,
                    "candles": visible_candles,
                },
                "dashboard": {
                    "version": self.dashboard_version,
                    "pages": self.dashboard_pages,
                    "patches": list(reversed(self.dashboard_patches[-20:])),
                },
                "report": self.report,
                "events": list(self.events)[:80],
                "findings": list(reversed(self.findings[-20:])),
                "decision_proposals": list(reversed(self.decision_proposals[-20:])),
                "decisions": list(reversed(self.decisions[-20:])),
                "consequence_receipts": list(
                    reversed(self.consequence_receipts[-20:])
                ),
                "context_revisions": list(reversed(self.context_revisions[-20:])),
                "decision_follow_up_runs": list(reversed(self.follow_up_runs[-20:])),
                "daily_history": self.daily_history,
                "meta_capabilities": [
                    "meta.synthetic_intraday.generate",
                    "meta.visualisation.render",
                    "meta.dashboard.patch",
                    "meta.package.compose",
                    "meta.agent.specialist.attach",
                ],
            }

    def close(self) -> None:
        self._stop_event.set()
        self.running = False
        if self._temporary_decision_root is not None:
            self._temporary_decision_root.cleanup()


class WorkflowCycleManager:
    def __init__(self, decision_store_factory=None) -> None:  # type: ignore[no-untyped-def]
        self.lock = threading.RLock()
        self.sessions: dict[str, SyntheticWorkflowSession] = {}
        self.decision_store_factory = decision_store_factory

    def create(self, configuration: dict[str, Any]) -> SyntheticWorkflowSession:
        digest = hashlib.sha256(
            f"{configuration['portfolio_id']}:{configuration['seed']}:{time.time_ns()}".encode()
        ).hexdigest()[:10]
        session_id = f"cycle-{digest}"
        store = self.decision_store_factory() if self.decision_store_factory else None
        session = SyntheticWorkflowSession(session_id, configuration, decision_store=store)
        with self.lock:
            self.sessions[session_id] = session
        return session

    def get(self, session_id: str) -> SyntheticWorkflowSession:
        with self.lock:
            session = self.sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def delete(self, session_id: str) -> None:
        with self.lock:
            session = self.sessions.pop(session_id, None)
        if session is None:
            raise KeyError(session_id)
        session.close()

    def find_by_proposal(self, proposal_id: str) -> SyntheticWorkflowSession | None:
        with self.lock:
            sessions = tuple(self.sessions.values())
        return next(
            (
                session
                for session in sessions
                if any(item["proposal_id"] == proposal_id for item in session.decision_proposals)
            ),
            None,
        )


workflow_cycle_manager = WorkflowCycleManager(decision_store)
