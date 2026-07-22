"""Reviewed, explicit policy bounds for deterministic analytics."""

from decimal import Decimal


DEFAULT_PERIODS_PER_YEAR = 252
MIN_CONFIDENCE_LEVEL = Decimal("0.90")
MAX_CONFIDENCE_LEVEL = Decimal("0.99")
TARGET_TAIL_OBSERVATIONS = 10
DECIMAL_PRECISION = 34

MISSING_OBSERVATION = "missing-observation"
MISSING_INTERVAL = "missing-interval"
INADEQUATE_TAIL_SAMPLE = "inadequate-tail-sample"
MISSING_SCENARIO_SHOCK = "missing-scenario-shock"
MISSING_CONSTITUENT_RETURN = "missing-constituent-return"
