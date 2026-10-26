"""Unit Test Suite for Phase 4: Stage 2 MCTS Combinatorial Solver.

Verifies UCT policy calculations, state immutability, 100% storage budget invariant compliance,
monotonic workload speedup (>1.0), and sub-1.5s execution latency for 500 rollouts.
"""

import math
import time
import pytest
from src.engine.db_connector import SQLiteConnector
from src.engine.tpch_schema import create_tpch_schema, populate_synthetic_tpch
from src.engine.tpch_workload import get_tpch_workload
from src.engine.hypo_cost_engine import HypoCostEngine, HypoIndex
from src.miner.candidate_miner import CandidateMiner
from src.mcts.node import MCTSNode
from src.mcts.uct_policy import UCTPolicy
from src.mcts.mcts_solver import MCTSSolver, MCTSResult


@pytest.fixture(scope="module")
def populated_db():
    """Initializes in-memory database with synthetic TPC-H data at SF=0.005 for fast unit testing."""
    conn = SQLiteConnector(":memory:", page_size=4096)
    create_tpch_schema(conn)
    populate_synthetic_tpch(conn, scale_factor=0.005, seed=42)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def candidate_pool(populated_db):
    """Mines a standard pool of 30-50 candidates for test queries."""
    workload = get_tpch_workload()
    miner = CandidateMiner(populated_db, min_pool_size=30, max_pool_size=50)
    return miner.mine_candidates(workload)


def test_uct_policy_formula():
    """Verifies UCT mathematical formula: Q + c * sqrt(ln(N) / n)."""
    # 1. Unvisited child must return infinity
    uct_inf = UCTPolicy.compute_uct(parent_visits=10, child_visits=0, child_q_value=0.5)
    assert math.isinf(uct_inf), "Unvisited child must return infinite UCT score."

    # 2. Visited child calculation check
    parent_n = 100
    child_n = 25
    q_val = 0.40
    c_const = 1.414

    expected = q_val + c_const * math.sqrt(math.log(parent_n) / child_n)
    actual = UCTPolicy.compute_uct(parent_n, child_n, q_val, c_const)
    assert pytest.approx(actual, rel=1e-4) == expected

    # 3. Higher visit count on child decreases exploration bonus
    uct_more_visits = UCTPolicy.compute_uct(parent_n, 50, q_val, c_const)
    assert uct_more_visits < actual, "Exploration bonus must diminish with more child visits."

    # 4. Zero parent visit edge case
    uct_zero_parent = UCTPolicy.compute_uct(parent_visits=0, child_visits=5, child_q_value=0.3)
    assert uct_zero_parent == 0.3


def test_uct_select_best_child():
    """Verifies select_best_child picks the child with highest UCT score."""
    parent = MCTSNode(state_indexes=frozenset(), cumulative_size_bytes=0, visits=10)
    
    idx1 = HypoIndex(table="lineitem", columns=("l_shipdate",), name="idx1")
    idx2 = HypoIndex(table="orders", columns=("o_orderdate",), name="idx2")

    child1 = MCTSNode(state_indexes=frozenset([idx1]), cumulative_size_bytes=4096, visits=8, total_reward=1.6) # Q = 0.2
    child2 = MCTSNode(state_indexes=frozenset([idx2]), cumulative_size_bytes=4096, visits=2, total_reward=0.8) # Q = 0.4

    parent.children = {idx1: child1, idx2: child2}

    best_action, best_child = UCTPolicy.select_best_child(parent, c_param=1.414)
    # child2 has higher Q (0.4 vs 0.2) and fewer visits (2 vs 8) -> higher UCT
    assert best_action == idx2
    assert best_child == child2


def test_node_expansion_and_hierarchy():
    """Verifies child state strictly contains parent state unioned with the selected index."""
    root = MCTSNode(state_indexes=frozenset(), cumulative_size_bytes=0)
    idx_a = HypoIndex(table="lineitem", columns=("l_orderkey",), name="idx_a")
    idx_b = HypoIndex(table="orders", columns=("o_custkey",), name="idx_b")

    root.untried_actions = [idx_a, idx_b]

    # Expand child A
    child_a = MCTSNode(
        state_indexes=root.state_indexes | {idx_a},
        cumulative_size_bytes=4096,
        parent=root,
        action_from_parent=idx_a,
        untried_actions=[idx_b]
    )
    root.add_child(idx_a, child_a)

    assert idx_a in root.children
    assert idx_a not in root.untried_actions
    assert child_a.state_indexes == frozenset([idx_a])
    assert child_a.parent == root

    # Backpropagate update
    child_a.update(0.75)
    assert child_a.visits == 1
    assert child_a.total_reward == 0.75
    assert child_a.q_value == 0.75
    assert child_a.best_reward == 0.75


def test_storage_budget_hard_invariant(populated_db, candidate_pool):
    """Verifies that across diverse budgets, cumulative size NEVER exceeds B (100% compliance)."""
    cost_engine = HypoCostEngine(populated_db)
    workload = get_tpch_workload()

    # Test across small, medium, and generous budgets
    budgets_to_test = [
        0,              # 0 budget -> must select 0 indexes
        8192,           # 8 KB budget -> at most 1-2 small indexes
        50 * 1024,      # 50 KB budget
        500 * 1024,     # 500 KB budget
        5 * 1024 * 1024 # 5 MB budget
    ]

    for budget in budgets_to_test:
        solver = MCTSSolver(
            cost_engine=cost_engine,
            candidate_pool=candidate_pool,
            storage_budget_bytes=budget,
            iterations=100
        )
        result = solver.solve(workload)

        # Invariant 1: Storage used must never exceed budget
        assert result.storage_used_bytes <= budget, (
            f"Budget violation: used {result.storage_used_bytes} bytes for budget {budget} bytes!"
        )
        # Invariant 2: Sum of individual index sizes equals storage_used_bytes
        total_calculated_bytes = sum(cost_engine.estimate_index_size(idx) for idx in result.best_indexes)
        assert total_calculated_bytes == result.storage_used_bytes
        assert result.budget_utilized_percent <= 100.0


def test_monotonic_improvement(populated_db, candidate_pool):
    """Verifies that MCTS selected index configuration strictly improves performance (Speedup > 1.0)."""
    cost_engine = HypoCostEngine(populated_db)
    workload = get_tpch_workload()

    # Use a generous 5 MB budget so optimal indexes can be chosen
    solver = MCTSSolver(
        cost_engine=cost_engine,
        candidate_pool=candidate_pool,
        storage_budget_bytes=5 * 1024 * 1024,
        iterations=300
    )
    result = solver.solve(workload)

    assert result.speedup_ratio > 1.0, (
        f"Expected speedup > 1.0, got speedup={result.speedup_ratio:.2f}"
    )
    assert result.best_cost < result.base_cost, (
        f"Optimized cost {result.best_cost} must be less than base cost {result.base_cost}"
    )
    assert result.cost_reduction_percent > 0.0
    assert len(result.best_indexes) > 0, "Expected at least one index to be selected under 5MB budget."


def test_execution_latency_sub_1_5_seconds(populated_db, candidate_pool):
    """Verifies 500 MCTS rollouts execute well under the 1.5s requirement."""
    cost_engine = HypoCostEngine(populated_db)
    workload = get_tpch_workload()

    solver = MCTSSolver(
        cost_engine=cost_engine,
        candidate_pool=candidate_pool,
        storage_budget_bytes=2 * 1024 * 1024,
        iterations=500
    )

    t0 = time.perf_counter()
    result = solver.solve(workload)
    elapsed_sec = time.perf_counter() - t0

    assert elapsed_sec < 1.5, f"Expected 500 rollouts in <1.5s, took {elapsed_sec:.3f}s"
    assert result.iterations_completed == 500
    assert result.search_time_ms > 0.0


def test_comparison_with_knapsack_baseline(populated_db, candidate_pool):
    """Verifies both MCTS and Knapsack baseline run successfully and respect storage budget."""
    cost_engine = HypoCostEngine(populated_db)
    workload = get_tpch_workload()
    budget = 1024 * 1024  # 1 MB

    solver = MCTSSolver(
        cost_engine=cost_engine,
        candidate_pool=candidate_pool,
        storage_budget_bytes=budget,
        iterations=200
    )

    mcts_res = solver.solve(workload)
    knap_res = solver.solve_knapsack_baseline(workload)

    assert mcts_res.storage_used_bytes <= budget
    assert knap_res.storage_used_bytes <= budget
    assert mcts_res.speedup_ratio >= 1.0
    assert knap_res.speedup_ratio >= 1.0
