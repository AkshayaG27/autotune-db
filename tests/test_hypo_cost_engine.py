"""Unit Test Suite for Component 2: Zero-Byte Hypothetical Cost Engine.

Verifies analytical cost calculations, monotonicity under relevant index additions,
zero improvement under irrelevant additions, leftmost prefix adherence, and sub-millisecond latency.
"""

import time
import pytest
from src.engine.db_connector import SQLiteConnector
from src.engine.tpch_schema import create_tpch_schema, populate_synthetic_tpch
from src.engine.tpch_workload import get_tpch_workload, get_query_by_id
from src.engine.hypo_cost_engine import HypoCostEngine, HypoIndex


@pytest.fixture(scope="module")
def populated_engine():
    """Initializes in-memory database with synthetic TPC-H data at SF=0.005 for fast unit testing."""
    connector = SQLiteConnector(":memory:", page_size=4096)
    create_tpch_schema(connector)
    populate_synthetic_tpch(connector, scale_factor=0.005, seed=42)
    yield connector
    connector.close()


def test_unindexed_cost_estimation(populated_engine):
    """Verifies baseline workload cost is positive and bounded."""
    engine = HypoCostEngine(populated_engine)
    workload = get_tpch_workload()

    base_cost = engine.estimate_workload_cost(workload, frozenset())
    assert base_cost > 0.0, "Base workload cost must be strictly positive."


def test_relevant_index_reduces_cost(populated_engine):
    """Verifies that adding a matching index monotonically reduces query and workload cost."""
    engine = HypoCostEngine(populated_engine)
    workload = get_tpch_workload()
    q6 = get_query_by_id("Q6")
    assert q6 is not None

    base_cost_q6 = engine.estimate_query_cost(q6, frozenset())

    # Add a highly relevant composite index for Q6: (l_shipdate, l_discount, l_quantity)
    composite_idx = HypoIndex(
        table="lineitem",
        columns=("l_shipdate", "l_discount", "l_quantity"),
        name="hypo_idx_q6_comp"
    )

    opt_cost_q6 = engine.estimate_query_cost(q6, frozenset([composite_idx]))
    assert opt_cost_q6 < base_cost_q6, (
        f"Expected cost reduction for Q6, got base={base_cost_q6}, opt={opt_cost_q6}"
    )

    # Check workload cost reduction
    base_workload = engine.estimate_workload_cost(workload, frozenset())
    opt_workload = engine.estimate_workload_cost(workload, frozenset([composite_idx]))
    assert opt_workload < base_workload


def test_irrelevant_index_yields_zero_delta(populated_engine):
    """Verifies that adding an index on an unqueried column yields zero cost delta."""
    engine = HypoCostEngine(populated_engine)
    q6 = get_query_by_id("Q6")

    # Q6 only queries lineitem. Adding an index on nation should yield 0 delta.
    irrelevant_idx = HypoIndex(
        table="nation",
        columns=("n_comment",),
        name="hypo_idx_nation_comment"
    )

    cost_delta = engine.estimate_cost_delta(q6, irrelevant_idx, frozenset())
    assert cost_delta == 0.0, f"Expected 0.0 cost delta for irrelevant index, got {cost_delta}"


def test_leftmost_prefix_rule(populated_engine):
    """Verifies that non-leading column indexes do not accelerate prefix-mismatched queries."""
    engine = HypoCostEngine(populated_engine)
    q1 = get_query_by_id("Q1")  # Filters primarily on l_shipdate

    # Index A: leading on l_discount (does not match Q1's filter on l_shipdate)
    non_leading_idx = HypoIndex(
        table="lineitem",
        columns=("l_discount", "l_quantity"),
        name="hypo_idx_discount"
    )
    delta_non_leading = engine.estimate_cost_delta(q1, non_leading_idx, frozenset())

    # Index B: leading on l_shipdate (matches Q1)
    leading_idx = HypoIndex(
        table="lineitem",
        columns=("l_shipdate", "l_discount"),
        name="hypo_idx_shipdate"
    )
    delta_leading = engine.estimate_cost_delta(q1, leading_idx, frozenset())

    assert delta_non_leading == 0.0, "Index without leftmost matching prefix should not trigger."
    assert delta_leading > 0.0, "Index with leftmost matching prefix must produce positive delta."


def test_sub_millisecond_evaluation_speed(populated_engine):
    """Verifies that workload cost evaluation runs in sub-millisecond time (<1ms per call)."""
    engine = HypoCostEngine(populated_engine)
    workload = get_tpch_workload()
    indexes = frozenset([
        HypoIndex("lineitem", ("l_shipdate", "l_discount"), "idx_1"),
        HypoIndex("orders", ("o_orderdate", "o_custkey"), "idx_2"),
        HypoIndex("customer", ("c_mktsegment",), "idx_3")
    ])

    iterations = 200
    start_t = time.perf_counter()
    for _ in range(iterations):
        _ = engine.estimate_workload_cost(workload, indexes)
    total_time_ms = (time.perf_counter() - start_t) * 1000.0

    avg_time_ms = total_time_ms / iterations
    assert avg_time_ms < 1.0, f"Average evaluation latency ({avg_time_ms:.3f}ms) exceeded 1.0ms threshold!"
