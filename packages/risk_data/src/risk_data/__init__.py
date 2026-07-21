"""Public Day 0 data-ingestion contracts."""

from .contracts import ConnectorDisabledError, ConnectorProtocol, DataQualityIssue, DatasetSnapshot, IngestionRun, NormalizedFundamentalRecord, NormalizedMarketRecord, QuerySpec, ValidationSummary
from .evidence import build_evidence_bundle, export_evidence
from .pipeline import IngestionEvidence, SyntheticIngestionResult, ingest_synthetic

__all__ = ["ConnectorDisabledError", "ConnectorProtocol", "DataQualityIssue", "DatasetSnapshot", "IngestionEvidence", "IngestionRun", "NormalizedFundamentalRecord", "NormalizedMarketRecord", "QuerySpec", "SyntheticIngestionResult", "ValidationSummary", "build_evidence_bundle", "export_evidence", "ingest_synthetic"]
