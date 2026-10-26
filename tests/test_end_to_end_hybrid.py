"""Unit & Integration Test Suite for Phase 5: Stage 3 Live DB Verification & 4-Way Ablation.

Verifies live physical index materialization, teardown cleanliness, strict budget compliance,
wall-clock speedup (>1.0), regression tabu backtracking, DBA dossier formatting, and 4-way ablation.
"""

import pytest
from src.engine.db_connector import SQLiteConnector
from src.engine.tpch_schema import create_tpch_schema, populate_synthetic_tpch
from src.engine.tpch_workload import get_tpch_workload
from src.engine.hypo_cost_engine import HypoCostEngine, HypoIndex
from src.miner.candidate_miner import CandidateMiner
from src.agent.react_controller import ReActVerificationController
from src.agent.dossier_generator import DossierGenerator
from src.benchmark.ablation_runner import AblationRunner


@pytest.fixture(scope="function")
def populated_db():
    """Initializes in-memory database with synthetic TPC-H data at SF=0.005 for fast testing."""
    conn = SQLiteConnector(":memory:", page_size=4096)
    create_tpch_schema(conn)
    populate_synthetic_tpch(conn, scale_factor=0.005, seed=42)
    yield conn
    conn.close()


def test_physical_materialization_and_teardown(populated_db):
    """Verifies that indexes are physically created in SQLite catalog and cleanly removed."""
    cost_engine = HypoCostEngine(populated_db)
    controller = ReActVerificationController(populated_db, cost_engine)

    indexes_to_test = [
        HypoIndex(table="lineitem", columns=("l_shipdate",), name="idx_test_mat_shipdate"),
        HypoIndex(table="orders", columns=("o_orderdate", "o_custkey"), name="idx_test_mat_orders")
    ]

    # 1. Materialize
    allocated = controller.materialize_indexes(indexes_to_test)
    assert len(allocated) == 2
    assert all(bytes_count > 0 for bytes_count in allocated.values())

    # Verify physical existence in sqlite_master
    cur_indexes = [
        row[0] for row in populated_db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_test_mat_%';"
        )
    ]
    assert "idx_test_mat_shipdate" in cur_indexes
    assert "idx_test_mat_orders" in cur_indexes

    # 2. Teardown
    controller.teardown_indexes(indexes_to_test)

    # Verify removal from sqlite_master
    cur_indexes_after = [
        row[0] for row in populated_db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_test_mat_%';"
        )
    ]
    assert len(cur_indexes_after) == 0


def test_live_db_storage_budget_adherence(populated_db):
    """Verifies that physical index sizes on live DB strictly respect storage budget B."""
    cost_engine = HypoCostEngine(populated_db)
    workload = get_tpch_workload()
    miner = CandidateMiner(populated_db, min_pool_size=30, max_pool_size=40)
    candidates = miner.mine_candidates(workload)

    budget_bytes = 200 * 1024  # 200 KB
    controller = ReActVerificationController(populated_db, cost_engine, max_reflection_cycles=1)

    result = controller.verify_and_tune(
        workload=workload,
        initial_candidates=candidates,
        storage_budget_bytes=budget_bytes,
        mcts_iterations=150
    )

    # Invariant: storage_used <= storage_budget
    assert result.storage_used_bytes <= budget_bytes, (
        f"Live storage violation: used {result.storage_used_bytes} bytes for budget {budget_bytes} bytes!"
    )
    assert result.budget_compliant is True

    # Teardown
    controller.teardown_indexes(result.active_indexes)


def test_live_workload_wallclock_speedup(populated_db):
    """Verifies that Stage 3 live verification achieves strictly positive wall-clock speedup (>1.0)."""
    cost_engine = HypoCostEngine(populated_db)
    workload = get_tpch_workload()
    miner = CandidateMiner(populated_db, min_pool_size=30, max_pool_size=40)
    candidates = miner.mine_candidates(workload)

    # Generous budget so optimal indexes are physically built
    budget_bytes = 3 * 1024 * 1024  # 3 MB
    controller = ReActVerificationController(
        populated_db,
        cost_engine,
        max_reflection_cycles=2,
        benchmark_repeats=3
    )

    result = controller.verify_and_tune(
        workload=workload,
        initial_candidates=candidates,
        storage_budget_bytes=budget_bytes,
        mcts_iterations=200
    )

    assert result.workload_speedup > 1.0, f"Expected speedup > 1.0, got {result.workload_speedup:.2f}x"
    assert result.total_opt_time_ms < result.total_base_time_ms
    assert len(result.active_indexes) > 0

    # Teardown
    controller.teardown_indexes(result.active_indexes)


def test_dossier_generation_completeness(populated_db):
    """Verifies DossierGenerator constructs a complete, valid DBA Markdown report."""
    cost_engine = HypoCostEngine(populated_db)
    workload = get_tpch_workload()
    miner = CandidateMiner(populated_db, min_pool_size=30, max_pool_size=35)
    candidates = miner.mine_candidates(workload)

    controller = ReActVerificationController(populated_db, cost_engine, max_reflection_cycles=1)
    result = controller.verify_and_tune(
        workload=workload,
        initial_candidates=candidates,
        storage_budget_bytes=1024 * 1024,
        mcts_iterations=100
    )

    dossier_md = DossierGenerator.generate_markdown_dossier(result)
    controller.teardown_indexes(result.active_indexes)

    assert len(dossier_md) > 300
    assert "# AutoTune-DB: DBA Physical Database Design Dossier" in dossier_md
    assert "CREATE INDEX IF NOT EXISTS" in dossier_md or len(result.active_indexes) == 0
    assert "Physical Storage Allocation Breakdown" in dossier_md
    assert "Query-Level Performance Benchmark Delta" in dossier_md
    assert "Cost-Based Optimizer (CBO) Plan Transformations" in dossier_md
    assert "Audit Verdict" in dossier_md


def test_four_way_ablation_runner(populated_db):
    """Verifies execution of the 4-way ablation framework and comparative metrics generation."""
    workload = get_tpch_workload()
    runner = AblationRunner(populated_db)

    metrics = runner.run_all(workload=workload, storage_budget_bytes=1024 * 1024)

    # 1. All 4 configurations must be present
    assert "Unindexed Baseline" in metrics
    assert "Pure Heuristic / LLM" in metrics
    assert "Pure MCTS (Blind Space)" in metrics
    assert "AutoTune-DB Hybrid" in metrics

    # 2. Check AutoTune-DB Hybrid metrics
    hybrid_m = metrics["AutoTune-DB Hybrid"]
    assert hybrid_m.speedup_ratio >= 1.0
    assert hybrid_m.budget_adherent is True
    assert hybrid_m.search_time_ms > 0.0

    # 3. Format markdown table check
    table_md = AblationRunner.format_markdown_table(metrics)
    assert "| Configuration | Workload Runtime (ms) |" in table_md
    assert "AutoTune-DB Hybrid" in table_md
    assert "Unindexed Baseline" in table_md
