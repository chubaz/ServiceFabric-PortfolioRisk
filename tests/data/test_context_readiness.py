from datetime import UTC, date, datetime

import duckdb

from risk_data import qualify_case_context_sources


def test_readiness_is_typed_point_in_time_and_never_associates() -> None:
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE TABLE ravenpack_events_linked (provider_id VARCHAR, dataset_revision VARCHAR, local_event_id VARCHAR, event_time TIMESTAMPTZ, available_at TIMESTAMPTZ, permno BIGINT)")
    connection.execute("CREATE TABLE ravenpack_integration_status (provider_id VARCHAR, publication_restriction VARCHAR)")
    connection.execute("INSERT INTO ravenpack_integration_status VALUES ('ravenpack', 'private_local')")
    connection.execute("CREATE TABLE ccm_links (permno BIGINT, gvkey VARCHAR, link_start DATE, link_end DATE)")
    connection.execute("CREATE TABLE compustat_quarterly (gvkey VARCHAR, observed_at DATE, available_at TIMESTAMPTZ, source_revision VARCHAR)")
    connection.execute("INSERT INTO ccm_links VALUES (101, '00101', DATE '2010-01-01', NULL)")
    connection.execute("INSERT INTO ravenpack_events_linked VALUES ('ravenpack', 'rp-1', 'e1', TIMESTAMPTZ '2015-01-05 10:00:00+00', TIMESTAMPTZ '2015-01-05 10:01:00+00', 101), ('ravenpack', 'rp-1', 'e2', TIMESTAMPTZ '2015-01-06 10:00:00+00', TIMESTAMPTZ '2015-02-01 10:00:00+00', 101)")
    connection.execute("INSERT INTO compustat_quarterly VALUES ('00101', DATE '2015-01-01', TIMESTAMPTZ '2015-01-03 10:00:00+00', 'cq-1')")

    result = qualify_case_context_sources(
        connection, batch_id="batch-1", portfolio_id="portfolio-1", permnos=(101,),
        start_date=date(2015, 1, 1), end_date=date(2015, 1, 10),
        retrospective_cutoff=datetime(2015, 1, 10, 23, 59, tzinfo=UTC),
        checked_at=datetime(2026, 8, 14, tzinfo=UTC),
    )

    assert result.association_execution == "not_authorized"
    assert result.association_count == 0
    assert result.sources[0].row_count == 2
    assert result.sources[0].eligible_row_count == 1
    assert result.preparation_steps[-1].state == "deferred"
    assert "amendment_state" in result.sources[0].missing_semantics
