from datetime import UTC, datetime

import duckdb

from risk_data import query_selected_case_context


def connection() -> duckdb.DuckDBPyConnection:
    value = duckdb.connect(":memory:")
    value.execute("""
        CREATE TABLE ravenpack_events_linked (
          provider_id VARCHAR, dataset_revision VARCHAR, source_event_id VARCHAR,
          local_event_id VARCHAR, event_time TIMESTAMPTZ, available_at TIMESTAMPTZ,
          permno BIGINT, event_type VARCHAR, topic VARCHAR, category VARCHAR,
          provider_entity_name VARCHAR, position_name VARCHAR, relevance DOUBLE,
          novelty DOUBLE, sentiment DOUBLE
        )
    """)
    value.execute("""
        CREATE TABLE ccm_links (
          permno BIGINT, gvkey VARCHAR, link_start DATE, link_end DATE
        )
    """)
    value.execute("""
        CREATE TABLE compustat_quarterly (
          gvkey VARCHAR, observed_at DATE, available_at TIMESTAMPTZ,
          source_revision VARCHAR, currency VARCHAR, total_assets DECIMAL(18,2),
          total_liabilities DECIMAL(18,2), common_equity DECIMAL(18,2),
          revenue DECIMAL(18,2), net_income DECIMAL(18,2)
        )
    """)
    value.execute("INSERT INTO ccm_links VALUES (101, '00101', DATE '2010-01-01', NULL)")
    return value


def test_query_returns_only_bounded_eligible_rows_and_counts_exclusions() -> None:
    with connection() as database:
        database.execute("""
            INSERT INTO ravenpack_events_linked VALUES
            ('ravenpack','rp-v1','source-1','local-1',TIMESTAMPTZ '2015-01-06 09:00:00+00',TIMESTAMPTZ '2015-01-06 09:01:00+00',101,'Earnings','Guidance','Results','Alpha','Alpha',0.9,0.8,-0.5),
            ('ravenpack','rp-v1','source-2','local-2',TIMESTAMPTZ '2015-01-07 09:00:00+00',NULL,101,'Credit','Liquidity','Credit','Alpha','Alpha',0.8,0.7,-0.4),
            ('ravenpack','rp-v1','source-3','local-3',TIMESTAMPTZ '2015-01-07 09:00:00+00',TIMESTAMPTZ '2015-01-10 09:00:00+00',101,'Other','Late','Other','Alpha','Alpha',0.5,0.2,0.0),
            ('ravenpack','rp-v1','outside','outside',TIMESTAMPTZ '2014-01-01 09:00:00+00',TIMESTAMPTZ '2014-01-01 09:01:00+00',101,'Other','Outside','Other','Alpha','Alpha',0.5,0.2,0.0)
        """)
        database.execute("""
            INSERT INTO compustat_quarterly VALUES
            ('00101',DATE '2014-12-31',TIMESTAMPTZ '2015-01-05 12:00:00+00','cq-v1','USD',1000,600,400,250,20),
            ('00101',DATE '2014-09-30',NULL,'cq-v1','USD',900,550,350,220,15)
        """)
        result = query_selected_case_context(
            database, permno=101,
            manifestation_time=datetime(2015, 1, 7, 12, tzinfo=UTC),
            retrospective_cutoff=datetime(2015, 1, 8, 23, 59, tzinfo=UTC),
            event_days_before=5, event_days_after=2,
            fundamental_lookback_quarters=4,
        )
    assert [item.source_record_id for item in result.event_rows] == ["source-1"]
    assert len(result.fundamental_rows) == 1
    assert result.excluded_missing_availability == 2
    assert result.excluded_after_cutoff == 1
    assert result.query_receipts == (
        "ravenpack-selected-context-v1",
        "compustat-selected-context-v1",
        "context-exclusion-counts-v1",
    )
    assert result.batch_digest.startswith("sha256:")


def test_query_is_deterministic_and_marks_provider_lifecycle_uncertainty() -> None:
    with connection() as database:
        database.execute("""
            INSERT INTO ravenpack_events_linked VALUES
            ('ravenpack','rp-v1','source-1','local-1',TIMESTAMPTZ '2015-01-07 09:00:00+00',TIMESTAMPTZ '2015-01-07 09:01:00+00',101,'Earnings','Guidance','Results','Alpha','Alpha',0.9,0.8,-0.5),
            ('ravenpack','rp-v1','source-1','local-1b',TIMESTAMPTZ '2015-01-07 09:00:00+00',TIMESTAMPTZ '2015-01-07 09:01:00+00',101,'Earnings','Guidance','Results','Alpha','Alpha',0.9,0.8,-0.5)
        """)
        arguments = dict(
            permno=101, manifestation_time=datetime(2015, 1, 7, 12, tzinfo=UTC),
            retrospective_cutoff=datetime(2015, 1, 8, 23, 59, tzinfo=UTC),
            event_days_before=5, event_days_after=2, fundamental_lookback_quarters=4,
        )
        first = query_selected_case_context(database, **arguments)
        second = query_selected_case_context(database, **arguments)
    assert first == second
    assert first.event_rows[0].duplicate_record_count == 2
    assert first.event_rows[0].quality_flags == (
        "duplicate_provider_records",
        "provider_lifecycle_unverified",
    )
