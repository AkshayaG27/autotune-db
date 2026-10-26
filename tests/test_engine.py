"""Test Suite for Phase 1: Database Engine Layer & TPC-H Harness.

Verifies schema creation, synthetic data populator, unindexed workload execution,
EXPLAIN QUERY PLAN detection, and physical index lifecycle with page tracking.
"""

import pytest
import time
from src.engine.db_connector import SQLiteConnector
from src.engine.tpch_schema import create_tpch_schema, drop_tpch_schema, populate_synthetic_tpch
from src.engine.tpch_workload import get_tpch_workload, get_query_by_id


@pytest.fixture(scope="module")
def populated_engine():
    """Initializes in-memory database with synthetic TPC-H data at SF=0.005 for fast unit testing."""
    connector = SQLiteConnector(":memory:", page_size=4096)
    create_tpch_schema(connector)
    counts = populate_synthetic_tpch(connector, scale_factor=0.005, seed=42)
    yield connector, counts
    connector.close()


def test_schema_creation_and_table_existence():
    """Verifies that all 8 TPC-H relational tables exist with expected schema."""
    connector = SQLiteConnector(":memory:")
    create_tpch_schema(connector)

    rows = connector.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    )
    table_names = [r[0] for r in rows]
    expected_tables = ["customer", "lineitem", "nation", "orders", "part", "partsupp", "region", "supplier"]
    assert table_names == expected_tables, f"Expected {expected_tables}, got {table_names}"

    # Verify primary keys on lineitem
    cur = connector._conn.cursor()
    cur.execute("PRAGMA table_info(lineitem);")
    cols = cur.fetchall()
    col_names = [c[1] for c in cols]
    assert "l_orderkey" in col_names
    assert "l_linenumber" in col_names
    assert "l_shipdate" in col_names
    assert "l_discount" in col_names
    assert "l_quantity" in col_names
    connector.close()


def test_synthetic_data_generation(populated_engine):
    """Verifies row counts and foreign key referential integrity in populated database."""
    connector, counts = populated_engine

    assert counts["region"] == 5
    assert counts["nation"] == 25
    assert counts["supplier"] >= 10
    assert counts["customer"] >= 50
    assert counts["part"] >= 50
    assert counts["orders"] >= 100
    assert counts["lineitem"] >= 200

    # Test referential integrity: Every lineitem must reference an existing order
    orphan_items = connector.execute(
        "SELECT COUNT(*) FROM lineitem WHERE l_orderkey NOT IN (SELECT o_orderkey FROM orders);"
    )[0][0]
    assert orphan_items == 0, f"Found {orphan_items} orphan line items!"

    # Every order must reference an existing customer
    orphan_orders = connector.execute(
        "SELECT COUNT(*) FROM orders WHERE o_custkey NOT IN (SELECT c_custkey FROM customer);"
    )[0][0]
    assert orphan_orders == 0, f"Found {orphan_orders} orphan orders!"


def test_unindexed_workload_execution(populated_engine):
    """Verifies all 5 analytical queries (Q1, Q3, Q6, Q10, Q12) execute cleanly and return rows."""
    connector, _ = populated_engine
    workload = get_tpch_workload()
    assert len(workload) == 5

    for query in workload:
        start_t = time.perf_counter()
        rows = connector.execute(query.sql)
        duration_ms = (time.perf_counter() - start_t) * 1000.0

        assert rows is not None, f"Query {query.query_id} returned None!"
        assert len(rows) > 0, f"Query {query.query_id} returned empty result set!"
        assert duration_ms >= 0.0, f"Query {query.query_id} had negative duration!"


def test_explain_query_plan_detects_scans(populated_engine):
    """Verifies EXPLAIN QUERY PLAN detects unindexed sequential scans on lineitem."""
    connector, _ = populated_engine
    q6 = get_query_by_id("Q6")
    assert q6 is not None

    plan_rows = connector.explain(q6.sql)
    assert len(plan_rows) > 0, "EXPLAIN QUERY PLAN returned no rows!"

    # In an unindexed database, lineitem must be scanned sequentially
    plan_details = " ".join([r[3] for r in plan_rows])
    assert "SCAN" in plan_details or "SCAN TABLE" in plan_details, (
        f"Expected SCAN in plan for unindexed Q6, got: {plan_details}"
    )


def test_index_lifecycle_and_size_tracking(populated_engine):
    """Tests physical index creation, size tracking (>0 bytes), active index query, and dropping."""
    connector, _ = populated_engine

    index_name = "idx_test_lineitem_shipdate"
    size_bytes = connector.create_index("lineitem", ["l_shipdate", "l_discount"], index_name)

    assert size_bytes > 0, f"Index size must be > 0 bytes, got {size_bytes}"
    assert connector.get_index_size_bytes(index_name) == size_bytes

    # Verify active index listing
    active = connector.get_active_indexes("lineitem")
    active_names = [idx["name"] for idx in active]
    assert index_name in active_names, f"Index {index_name} not found in active indexes: {active_names}"

    # Drop index and verify cleanup
    connector.drop_index(index_name)
    active_after = connector.get_active_indexes("lineitem")
    active_after_names = [idx["name"] for idx in active_after]
    assert index_name not in active_after_names, f"Index {index_name} was not dropped!"


def test_table_cardinality_and_row_count(populated_engine):
    """Verifies calculation of column cardinality and row counts."""
    connector, _ = populated_engine

    total_rows = connector.get_table_row_count("lineitem")
    assert total_rows > 0

    # l_orderkey should have relatively high cardinality
    card_orderkey = connector.get_table_cardinality("lineitem", "l_orderkey")
    assert 0.0 < card_orderkey <= 1.0

    # l_returnflag has only 3 distinct values ('R', 'A', 'N'), so cardinality ratio should be low
    card_returnflag = connector.get_table_cardinality("lineitem", "l_returnflag")
    assert 0.0 < card_returnflag < 0.10, f"l_returnflag cardinality unexpectedly high: {card_returnflag}"
