"""Unit Test Suite for Phase 3: Stage 1 AST Semantic Predicate Miner & Candidate Pool Generator.

Verifies SQL predicate extraction, Leftmost Prefix / Equality-First ordering,
candidate pool size bounds (30 <= |C| <= 50), and inclusion of crucial index keys.
"""

import time
import pytest
from src.engine.db_connector import SQLiteConnector
from src.engine.tpch_workload import get_tpch_workload, get_query_by_id
from src.miner.ast_visitor import SQLPredicateVisitor, PredicateOp
from src.miner.candidate_miner import CandidateMiner
from src.engine.hypo_cost_engine import HypoIndex


@pytest.fixture(scope="module")
def connector():
    conn = SQLiteConnector(":memory:")
    yield conn
    conn.close()


def test_extract_predicates_q6():
    """Verifies predicate extraction on Q6 (conjunction of shipdate, discount, quantity)."""
    q6 = get_query_by_id("Q6")
    assert q6 is not None

    summary = SQLPredicateVisitor.extract_predicates(q6.sql, q6.query_id)
    assert "lineitem" in summary.tables

    filter_cols = {p.column: p.op_type for p in summary.filter_predicates if p.table == "lineitem"}
    assert "l_shipdate" in filter_cols
    assert "l_discount" in filter_cols
    assert "l_quantity" in filter_cols
    assert filter_cols["l_shipdate"] == PredicateOp.RANGE
    assert filter_cols["l_discount"] == PredicateOp.RANGE
    assert filter_cols["l_quantity"] == PredicateOp.RANGE


def test_extract_predicates_q3_joins():
    """Verifies join and filter predicate extraction on Q3 (customer, orders, lineitem)."""
    q3 = get_query_by_id("Q3")
    assert q3 is not None

    summary = SQLPredicateVisitor.extract_predicates(q3.sql, q3.query_id)
    assert "customer" in summary.tables
    assert "orders" in summary.tables
    assert "lineitem" in summary.tables

    join_cols = {(p.table, p.column) for p in summary.join_predicates}
    assert ("customer", "c_custkey") in join_cols
    assert ("orders", "o_custkey") in join_cols
    assert ("orders", "o_orderkey") in join_cols
    assert ("lineitem", "l_orderkey") in join_cols

    # Check filter predicate c_mktsegment is equality
    c_mkt = next((p for p in summary.filter_predicates if p.column == "c_mktsegment"), None)
    assert c_mkt is not None
    assert c_mkt.op_type == PredicateOp.EQUALITY


def test_equality_first_column_ordering(connector):
    """Verifies that equality and join columns are ordered before range columns."""
    miner = CandidateMiner(connector)

    col_op_types = {
        ("lineitem", "l_shipdate"): PredicateOp.RANGE,
        ("lineitem", "l_returnflag"): PredicateOp.EQUALITY,
        ("lineitem", "l_orderkey"): PredicateOp.JOIN,
    }

    # Case A: Range + Equality -> Equality must precede Range
    ordered_a = miner._order_columns_equality_first("lineitem", ["l_shipdate", "l_returnflag"], col_op_types)
    assert ordered_a == ["l_returnflag", "l_shipdate"]

    # Case B: Join + Range -> Join must precede Range
    ordered_b = miner._order_columns_equality_first("lineitem", ["l_shipdate", "l_orderkey"], col_op_types)
    assert ordered_b == ["l_orderkey", "l_shipdate"]

    # Case C: Dual Equality -> Higher cardinality must precede lower cardinality
    ordered_c = miner._order_columns_equality_first("lineitem", ["l_returnflag", "l_orderkey"], col_op_types)
    assert ordered_c == ["l_orderkey", "l_returnflag"]


def test_mined_candidate_pool_bounded_size(connector):
    """Verifies that mined candidate pool strictly satisfies 30 <= |C| <= 50."""
    miner = CandidateMiner(connector, min_pool_size=30, max_pool_size=50)
    workload = get_tpch_workload()

    candidates = miner.mine_candidates(workload)

    assert isinstance(candidates, list)
    assert 30 <= len(candidates) <= 50, f"Expected 30 <= |C| <= 50, got {len(candidates)}"

    # Verify all items are HypoIndex instances with unique keys
    keys = set()
    for c in candidates:
        assert isinstance(c, HypoIndex)
        assert len(c.columns) >= 1
        assert c.key not in keys, f"Duplicate candidate key detected: {c.key}"
        keys.add(c.key)


def test_candidate_pool_contains_crucial_workload_indexes(connector):
    """Verifies that essential analytical index keys are present in candidate pool."""
    miner = CandidateMiner(connector)
    workload = get_tpch_workload()

    candidates = miner.mine_candidates(workload)
    candidate_keys = {c.key for c in candidates}

    # Crucial Q6 composite index or its prefix
    has_q6_candidate = any("l_shipdate" in c.columns and "l_discount" in c.columns for c in candidates if c.table == "lineitem")
    assert has_q6_candidate, "Candidate pool missing Q6 shipdate-discount composite index!"

    # Crucial Q3 customer filter-join candidate
    has_q3_cust = any("c_mktsegment" in c.columns and "c_custkey" in c.columns for c in candidates if c.table == "customer")
    assert has_q3_cust, "Candidate pool missing Q3 customer composite index!"

    # Crucial Q3/Q10 lineitem join key
    has_lineitem_orderkey = any(c.table == "lineitem" and c.columns[0] == "l_orderkey" for c in candidates)
    assert has_lineitem_orderkey, "Candidate pool missing lineitem join key index!"


def test_mining_latency_sub_100ms(connector):
    """Verifies that candidate mining executes in <100ms."""
    miner = CandidateMiner(connector)
    workload = get_tpch_workload()

    start_t = time.perf_counter()
    candidates = miner.mine_candidates(workload)
    duration_ms = (time.perf_counter() - start_t) * 1000.0

    assert duration_ms < 100.0, f"Candidate mining latency ({duration_ms:.2f}ms) exceeded 100ms threshold!"
    assert len(candidates) >= 30
