"""Public Day 0 data-ingestion contracts."""

from .contracts import ConnectorDisabledError, ConnectorProtocol, DataQualityIssue, DatasetSnapshot, IngestionRun, NormalizedFundamentalRecord, NormalizedMarketRecord, QuerySpec, ValidationSummary
from .pipeline import IngestionEvidence, SyntheticIngestionResult, ingest_synthetic

__all__ = ["ConnectorDisabledError", "ConnectorProtocol", "DataQualityIssue", "DatasetSnapshot", "IngestionEvidence", "IngestionRun", "NormalizedFundamentalRecord", "NormalizedMarketRecord", "QuerySpec", "SyntheticIngestionResult", "ValidationSummary", "ingest_synthetic"]
