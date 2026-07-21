"""The finite Day 0 capability catalog."""

from .contracts import CapabilityDescriptor


ORDER_AND_BROKER_EFFECTS = ("order_submission", "broker_connectivity")

CAPABILITY_DESCRIPTORS = (
    CapabilityDescriptor(
        capability_id="risk.capability.news_sentiment",
        objective="Summarize supplied news evidence without fabricating observations.",
        input_contract="EvidenceReference[] and JSON-safe research context.",
        output_contract="CapabilityOutcome with preserved evidence references and disclosures.",
        allowed_effects=("draft_finding",),
        denied_effects=ORDER_AND_BROKER_EFFECTS,
    ),
    CapabilityDescriptor(
        capability_id="risk.capability.market_data",
        objective="Describe supplied market-data evidence without fetching provider data.",
        input_contract="EvidenceReference[] and JSON-safe observation context.",
        output_contract="CapabilityOutcome with preserved evidence references and quality warnings.",
        allowed_effects=("draft_finding",),
        denied_effects=ORDER_AND_BROKER_EFFECTS,
    ),
    CapabilityDescriptor(
        capability_id="risk.capability.portfolio_exposure",
        objective="Describe supplied portfolio exposure evidence without calculating analytics.",
        input_contract="EvidenceReference[] and JSON-safe snapshot context.",
        output_contract="CapabilityOutcome with preserved evidence references and limitations.",
        allowed_effects=("draft_finding",),
        denied_effects=ORDER_AND_BROKER_EFFECTS,
    ),
    CapabilityDescriptor(
        capability_id="risk.capability.alert_recommendation",
        objective="Draft a review-required alert from supplied evidence; it is not investment advice.",
        input_contract="EvidenceReference[] and JSON-safe finding context.",
        output_contract="CapabilityOutcome with preserved evidence references and human-review disclosure.",
        allowed_effects=("draft_alert",),
        denied_effects=ORDER_AND_BROKER_EFFECTS,
    ),
)

CAPABILITY_BY_ID = {item.capability_id: item for item in CAPABILITY_DESCRIPTORS}
