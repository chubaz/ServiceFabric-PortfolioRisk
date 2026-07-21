"""Deterministic, local-only Wave 0B capability registry."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from statistics import mean, pstdev
from typing import Any, Generic, Literal, TypeVar

from pydantic import Field, field_validator, model_validator

from risk_data import IngestionRun, NormalizedMarketRecord
from risk_domain import CashBalance, ExposureSnapshot, PortfolioSnapshot, Position, PositionExposure, SourceReference
from risk_planning import PlanningCatalog

from .contracts import CapabilityContract, EvidenceReference


DECIMAL_CONTEXT_PRECISION = 34
ResultValue = TypeVar("ResultValue")


class CapabilityResult(CapabilityContract, Generic[ResultValue]):
    """A local capability result with explicit evidence and no effects."""

    capability_id: str = Field(pattern=r"^(planning|data|portfolio|market|news|alert)\.[a-z_]+\.[a-z_]+$")
    status: Literal["succeeded", "failed", "stopped"] = "succeeded"
    data: ResultValue | None = None
    evidence_references: tuple[EvidenceReference, ...]
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    findings: tuple["MonitoringFinding", ...] = ()

    @field_validator("effects")
    @classmethod
    def no_effects_are_permitted(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values:
            raise ValueError("Wave 0B capabilities must not generate effects")
        return values


class PositionSpecification(CapabilityContract):
    instrument_id: str = Field(min_length=1)
    quantity: Decimal
    currency: str = "USD"


class PortfolioSnapshotRequest(CapabilityContract):
    snapshot_id: str = Field(min_length=1)
    as_of: datetime
    base_currency: str = "USD"
    positions: tuple[PositionSpecification, ...] = Field(min_length=1)
    cash_balances: tuple[CashBalance, ...] = ()
    normalized_observations: tuple[NormalizedMarketRecord, ...] = Field(min_length=1)
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)

    @field_validator("as_of")
    @classmethod
    def as_of_is_explicit_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware and explicit")
        return value.astimezone(UTC)


class ExposureSummaryRequest(CapabilityContract):
    snapshot_id: str = Field(min_length=1)
    portfolio_snapshot: PortfolioSnapshot
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class AnomalyDetectionRequest(CapabilityContract):
    normalized_observations: tuple[NormalizedMarketRecord, ...] = Field(min_length=2)
    percentage_threshold: Decimal | None = Field(default=None, gt=Decimal("0"))
    z_score_threshold: Decimal | None = Field(default=None, gt=Decimal("0"))
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def at_least_one_threshold_is_provided(self) -> "AnomalyDetectionRequest":
        if self.percentage_threshold is None and self.z_score_threshold is None:
            raise ValueError("a percentage or z-score threshold is required")
        return self


class Anomaly(CapabilityContract):
    instrument_id: str
    observed_at: datetime
    simple_return: Decimal
    triggered_by: tuple[str, ...]
    z_score: Decimal | None = None


class AnomalyReport(CapabilityContract):
    anomalies: tuple[Anomaly, ...]
    evaluated_returns: int


class MonitoringFinding(CapabilityContract):
    finding_id: str
    kind: Literal["market_anomaly", "concentration", "news_event"]
    summary: str
    evidence_references: tuple[EvidenceReference, ...]
    severity: Literal["info", "warning", "high"] = "warning"


class SyntheticNewsEvent(CapabilityContract):
    event_id: str
    instrument_id: str
    headline: str
    sentiment: Literal["positive", "negative", "neutral"]
    relevance: Literal["low", "medium", "high"]
    synthetic: Literal[True] = True
    synthetic_label: Literal["synthetic"] = "synthetic"


class NewsClassificationRequest(CapabilityContract):
    event: SyntheticNewsEvent
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class NewsClassification(CapabilityContract):
    event_id: str
    instrument_id: str
    sentiment: Literal["positive", "negative", "neutral"]
    relevance: Literal["low", "medium", "high"]
    synthetic_disclosure: str


class AlertDraft(CapabilityContract):
    alert_id: str
    summary: str
    suggested_next_steps: tuple[Literal["investigation", "scenario_analysis", "watch_status", "rebalance_analysis"], ...]
    human_review_required: Literal[True] = True
    executable_order_recommendation: Literal[False] = False


class AlertSynthesisRequest(CapabilityContract):
    market_output: CapabilityResult[Any]
    exposure_output: CapabilityResult[Any]
    news_output: CapabilityResult[Any]
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class DecisionPoint(CapabilityContract):
    decision_id: str
    alert_id: str
    decision: Literal["approve", "reject", "request_changes"]
    rationale: str
    human_reviewer_id: str


class AlertReviewRequest(CapabilityContract):
    draft: AlertDraft
    decision_point: DecisionPoint
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class AlertReview(CapabilityContract):
    draft: AlertDraft
    decision_point: DecisionPoint


class KnowledgeDueRequest(CapabilityContract):
    catalog: PlanningCatalog
    offset_minutes: int = Field(ge=0)
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


class SyntheticIngestRequest(CapabilityContract):
    ingestion_run: IngestionRun
    evidence_references: tuple[EvidenceReference, ...] = Field(min_length=1)


def _source_references(observations: tuple[NormalizedMarketRecord, ...]) -> tuple[SourceReference, ...]:
    sources = [record.to_market_observation().sources[0] for record in observations]
    unique = {(item.source_id, item.reference): item for item in sources}
    return tuple(sorted(unique.values(), key=lambda item: (item.source_id, item.reference)))


def create_portfolio_snapshot(request: PortfolioSnapshotRequest) -> CapabilityResult[PortfolioSnapshot]:
    """Create a content-addressed snapshot from explicit observations and positions."""
    prices: dict[str, NormalizedMarketRecord] = {}
    for observation in request.normalized_observations:
        if observation.observed_at <= request.as_of and (
            observation.instrument_id not in prices or observation.observed_at > prices[observation.instrument_id].observed_at
        ):
            prices[observation.instrument_id] = observation
    positions: list[Position] = []
    for specification in request.positions:
        observation = prices.get(specification.instrument_id)
        if observation is None or observation.price is None:
            raise ValueError(f"missing price for position {specification.instrument_id}; no zero value is inferred")
        if observation.currency != request.base_currency or specification.currency != request.base_currency:
            raise ValueError("Wave 0B snapshot creation requires base-currency positions and observations")
        positions.append(Position(instrument_id=specification.instrument_id, quantity=specification.quantity, price=observation.price, market_value=specification.quantity * observation.price, currency=specification.currency))
    snapshot = PortfolioSnapshot(snapshot_id=request.snapshot_id, as_of=request.as_of, base_currency=request.base_currency, positions=tuple(positions), cash_balances=request.cash_balances, market_observations=tuple(item.to_market_observation() for item in request.normalized_observations), sources=_source_references(request.normalized_observations))
    return CapabilityResult(capability_id="portfolio.snapshot.create", data=snapshot, evidence_references=request.evidence_references, assumptions=("Prices are the latest supplied observations at or before the explicit as_of timestamp.",), limitations=("No price conversion or external data retrieval was performed.",))


def summarize_exposure(request: ExposureSummaryRequest) -> CapabilityResult[ExposureSnapshot]:
    """Calculate exposure strictly from a supplied immutable portfolio snapshot."""
    portfolio = request.portfolio_snapshot
    with localcontext() as context:
        context.prec = DECIMAL_CONTEXT_PRECISION
        nav = sum((position.market_value for position in portfolio.positions), start=Decimal("0")) + sum((balance.amount for balance in portfolio.cash_balances), start=Decimal("0"))
        if nav <= 0:
            raise ValueError("portfolio NAV must be positive")
        position_exposures = tuple(PositionExposure(instrument_id=position.instrument_id, market_value=position.market_value, weight=position.market_value / nav) for position in portfolio.positions)
        gross = sum((abs(item.weight) for item in position_exposures), start=Decimal("0"))
        net = sum((item.weight for item in position_exposures), start=Decimal("0"))
        largest = max((abs(item.weight) for item in position_exposures), default=Decimal("0"))
        cash_weight = sum((balance.amount for balance in portfolio.cash_balances), start=Decimal("0")) / nav
    exposure = ExposureSnapshot(snapshot_id=request.snapshot_id, as_of=portfolio.as_of, portfolio_snapshot=portfolio, nav=nav, gross_exposure=gross, net_exposure=net, largest_position_weight=largest, cash_weight=cash_weight, position_exposures=position_exposures)
    largest = max(exposure.position_exposures, key=lambda item: abs(item.weight), default=None)
    findings = () if largest is None or abs(largest.weight) <= Decimal("0.40") else (MonitoringFinding(finding_id=f"concentration:{largest.instrument_id}:{request.snapshot_id}", kind="concentration", summary=f"{largest.instrument_id} weight {largest.weight} exceeds the 40% largest-position limit.", evidence_references=request.evidence_references, severity="high"),)
    return CapabilityResult(capability_id="portfolio.exposure.summarize", data=exposure, evidence_references=request.evidence_references, assumptions=("All position and cash values are already in the portfolio base currency.",), limitations=("This is a deterministic arithmetic summary, not investment advice.",), findings=findings)


def detect_market_anomalies(request: AnomalyDetectionRequest) -> CapabilityResult[AnomalyReport]:
    """Calculate simple returns and flag threshold breaches without imputing missing values."""
    grouped: dict[str, list[NormalizedMarketRecord]] = {}
    for observation in request.normalized_observations:
        grouped.setdefault(observation.instrument_id, []).append(observation)
    anomalies: list[Anomaly] = []
    warnings: list[str] = []
    evaluated_returns = 0
    for instrument_id, records in sorted(grouped.items()):
        prior: NormalizedMarketRecord | None = None
        returns: list[tuple[NormalizedMarketRecord, Decimal]] = []
        for record in sorted(records, key=lambda item: item.observed_at):
            if record.price is None:
                warnings.append(f"{instrument_id} has a missing observation at {record.observed_at.isoformat()}; no return was inferred.")
                prior = None
                continue
            if prior is not None and prior.price is not None:
                simple_return = (record.price - prior.price) / prior.price
                returns.append((record, simple_return))
                evaluated_returns += 1
            prior = record
        return_values = [item[1] for item in returns]
        z_scores: dict[datetime, Decimal] = {}
        if request.z_score_threshold is not None and len(return_values) >= 3:
            average = Decimal(str(mean(return_values)))
            deviation = Decimal(str(pstdev(return_values)))
            if deviation != 0:
                z_scores = {record.observed_at: abs((simple_return - average) / deviation) for record, simple_return in returns}
        elif request.z_score_threshold is not None:
            warnings.append(f"{instrument_id} has insufficient complete returns for z-score evaluation.")
        for record, simple_return in returns:
            triggers: list[str] = []
            if request.percentage_threshold is not None and abs(simple_return) >= request.percentage_threshold:
                triggers.append("percentage")
            z_score = z_scores.get(record.observed_at)
            if z_score is not None and request.z_score_threshold is not None and z_score >= request.z_score_threshold:
                triggers.append("z_score")
            if triggers:
                anomalies.append(Anomaly(instrument_id=instrument_id, observed_at=record.observed_at, simple_return=simple_return, triggered_by=tuple(triggers), z_score=z_score))
    report = AnomalyReport(anomalies=tuple(sorted(anomalies, key=lambda item: (item.instrument_id, item.observed_at))), evaluated_returns=evaluated_returns)
    findings = tuple(MonitoringFinding(finding_id=f"anomaly:{item.instrument_id}:{item.observed_at.isoformat()}", kind="market_anomaly", summary=f"{item.instrument_id} simple return {item.simple_return} triggered {', '.join(item.triggered_by)}.", evidence_references=request.evidence_references, severity="high") for item in report.anomalies)
    return CapabilityResult(capability_id="market.anomaly.detect", data=report, evidence_references=request.evidence_references, assumptions=("Simple returns use adjacent complete supplied observations only.",), warnings=tuple(warnings), limitations=("No missing observation is converted to a zero return; no external market data is used.",), findings=findings)


def classify_news_event(request: NewsClassificationRequest) -> CapabilityResult[NewsClassification]:
    event = request.event
    classification = NewsClassification(event_id=event.event_id, instrument_id=event.instrument_id, sentiment=event.sentiment, relevance=event.relevance, synthetic_disclosure="This news event and classification are synthetic.")
    finding = MonitoringFinding(finding_id=f"news:{event.event_id}", kind="news_event", summary=f"Synthetic {event.sentiment} news event for {event.instrument_id} with {event.relevance} relevance.", evidence_references=request.evidence_references, severity="warning")
    return CapabilityResult(capability_id="news.event.classify", data=classification, evidence_references=request.evidence_references, assumptions=("Classification uses explicitly supplied synthetic labels only.",), limitations=("No news provider or sentiment model was called.",), findings=(finding,))


def synthesize_alert_draft(request: AlertSynthesisRequest) -> CapabilityResult[AlertDraft]:
    inputs = (request.market_output, request.exposure_output, request.news_output)
    if any(item.status != "succeeded" for item in inputs):
        return CapabilityResult(capability_id="alert.draft.synthesize", status="stopped", evidence_references=request.evidence_references, warnings=("Alert synthesis stopped because an upstream capability did not succeed.",))
    draft = AlertDraft(alert_id="alert:" + "-".join(item.capability_id.replace(".", "-") for item in inputs), summary="Review required: synthetic market anomaly, concentration, and news findings require investigation.", suggested_next_steps=("investigation", "scenario_analysis", "watch_status", "rebalance_analysis"))
    return CapabilityResult(capability_id="alert.draft.synthesize", data=draft, evidence_references=request.evidence_references, assumptions=("Alert content is synthesized only from supplied capability outputs.",), limitations=("The draft is not investment advice and cannot submit an order.",))


def review_alert_draft(request: AlertReviewRequest) -> CapabilityResult[AlertReview]:
    if request.decision_point.alert_id != request.draft.alert_id:
        raise ValueError("decision point must reference the reviewed alert draft")
    return CapabilityResult(capability_id="alert.draft.review", data=AlertReview(draft=request.draft, decision_point=request.decision_point), evidence_references=request.evidence_references, limitations=("Review records a decision only and creates no external effect.",))


def list_due_knowledge(request: KnowledgeDueRequest) -> CapabilityResult[tuple[Any, ...]]:
    due = tuple(item for item in request.catalog.knowledge_products if item.draft_deadline.offset_minutes <= request.offset_minutes)
    return CapabilityResult(capability_id="planning.knowledge.list_due", data=due, evidence_references=request.evidence_references, limitations=("Due status is evaluated only against the supplied deterministic offset.",))


def ingest_synthetic(request: SyntheticIngestRequest) -> CapabilityResult[IngestionRun]:
    return CapabilityResult(capability_id="data.synthetic.ingest", data=request.ingestion_run, evidence_references=request.evidence_references, assumptions=("The supplied ingestion run is already local and synthetic.",), limitations=("This registry does not contact providers or perform ingestion itself.",))


CapabilityHandler = Callable[[Any], CapabilityResult[Any]]


class CapabilityStopped(Exception):
    """A deterministic signal that a capability could not continue."""


class CapabilityInvocationRecord(CapabilityContract):
    sequence: int
    capability_id: str
    status: Literal["succeeded", "failed", "stopped"]
    evidence_references: tuple[EvidenceReference, ...]


class CapabilityRegistry:
    """Finite deterministic dispatcher for registered Wave 0B capabilities."""

    def __init__(self, handlers: dict[str, CapabilityHandler] | None = None) -> None:
        self._handlers = handlers or {
            "planning.knowledge.list_due": list_due_knowledge,
            "data.synthetic.ingest": ingest_synthetic,
            "portfolio.snapshot.create": create_portfolio_snapshot,
            "portfolio.exposure.summarize": summarize_exposure,
            "market.anomaly.detect": detect_market_anomalies,
            "news.event.classify": classify_news_event,
            "alert.draft.synthesize": synthesize_alert_draft,
            "alert.draft.review": review_alert_draft,
        }
        if len(self._handlers) != len(set(self._handlers)):
            raise ValueError("capability IDs must be unique")
        self._request_types: dict[str, type[CapabilityContract]] = {
            "planning.knowledge.list_due": KnowledgeDueRequest,
            "data.synthetic.ingest": SyntheticIngestRequest,
            "portfolio.snapshot.create": PortfolioSnapshotRequest,
            "portfolio.exposure.summarize": ExposureSummaryRequest,
            "market.anomaly.detect": AnomalyDetectionRequest,
            "news.event.classify": NewsClassificationRequest,
            "alert.draft.synthesize": AlertSynthesisRequest,
            "alert.draft.review": AlertReviewRequest,
        }
        self._history: list[CapabilityInvocationRecord] = []

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    @property
    def invocation_history(self) -> tuple[CapabilityInvocationRecord, ...]:
        return tuple(self._history)

    def invoke(self, capability_id: str, request: Any) -> CapabilityResult[Any]:
        try:
            handler = self._handlers[capability_id]
        except KeyError as error:
            raise ValueError(f"capability is not registered: {capability_id}") from error
        request_type = self._request_types.get(capability_id)
        if request_type is not None and not isinstance(request, request_type):
            raise TypeError(f"{capability_id} requires {request_type.__name__}")
        try:
            result = handler(request)
        except CapabilityStopped as error:
            result = CapabilityResult(capability_id=capability_id, status="stopped", evidence_references=getattr(request, "evidence_references", ()), warnings=(str(error),))
        except Exception as error:
            result = CapabilityResult(capability_id=capability_id, status="failed", evidence_references=getattr(request, "evidence_references", ()), warnings=(str(error),))
        if result.capability_id != capability_id:
            raise ValueError("capability handler returned a mismatched capability ID")
        self._history.append(CapabilityInvocationRecord(sequence=len(self._history), capability_id=capability_id, status=result.status, evidence_references=result.evidence_references))
        return result


DEFAULT_CAPABILITY_REGISTRY = CapabilityRegistry()
