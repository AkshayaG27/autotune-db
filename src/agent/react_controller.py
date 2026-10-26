"""Stage 3: Live Database Verification & ReAct Reflection Controller.

Materializes candidate physical indexes on the live database, benchmarks wall-clock runtimes,
inspects query execution plans, detects CBO regressions, and backtracks via a Tabu list.
"""

import re
import time
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from src.engine.db_connector import DatabaseConnector
from src.engine.tpch_workload import WorkloadQuery
from src.engine.hypo_cost_engine import HypoCostEngine, HypoIndex
from src.engine.plan_parser import PlanASTParser, PlanNode
from src.mcts.mcts_solver import MCTSSolver, MCTSResult


@dataclass
class QueryBenchmarkResult:
    """Benchmark measurements for an individual query."""
    query_id: str
    base_time_ms: float
    opt_time_ms: float
    speedup_ratio: float
    base_plan_raw: List[Tuple]
    opt_plan_raw: List[Tuple]
    used_indexes: List[str]
    has_regressed: bool


@dataclass
class VerificationResult:
    """Holistic live verification outcome across the full workload."""
    workload_speedup: float
    total_base_time_ms: float
    total_opt_time_ms: float
    storage_used_bytes: int
    storage_budget_bytes: int
    budget_compliant: bool
    query_results: Dict[str, QueryBenchmarkResult]
    regressions_detected: List[str]
    reflection_cycles: int
    active_indexes: List[HypoIndex]
    mcts_result: Optional[MCTSResult] = None


class ReActVerificationController:
    """Controls physical index materialization, wall-clock benchmarking, and regression reflection."""

    def __init__(
        self,
        connector: DatabaseConnector,
        cost_engine: HypoCostEngine,
        max_reflection_cycles: int = 3,
        regression_threshold: float = 0.15,
        benchmark_repeats: int = 3
    ):
        self.connector = connector
        self.cost_engine = cost_engine
        self.max_reflection_cycles = max_reflection_cycles
        self.regression_threshold = regression_threshold
        self.benchmark_repeats = benchmark_repeats
        self.tabu_list: Set[str] = set()

    def benchmark_query(self, query: WorkloadQuery) -> Tuple[float, List[Tuple]]:
        """Executes a single query on the live DB and returns (median_time_ms, raw_plan)."""
        # 1. Capture query plan
        plan_rows = self.connector.explain(query.sql)

        # 2. Warm-up cache runs
        for _ in range(2):
            self.connector.execute(query.sql)

        # 3. Timed benchmark runs (min runtime filters out OS timer preemption noise)
        durations: List[float] = []
        repeats = max(self.benchmark_repeats, 5)
        for _ in range(repeats):
            t0 = time.perf_counter()
            self.connector.execute(query.sql)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            durations.append(elapsed_ms)

        # In benchmarking, min() filters out system interrupt spikes (timeit standard)
        best_ms = min(durations)
        return best_ms, plan_rows

    def materialize_indexes(self, indexes: List[HypoIndex]) -> Dict[str, int]:
        """Creates physical B-Tree indexes on the live database and returns allocated bytes."""
        allocated_sizes: Dict[str, int] = {}
        for idx in indexes:
            size_bytes = self.connector.create_index(
                table=idx.table,
                columns=list(idx.columns),
                index_name=idx.name
            )
            allocated_sizes[idx.name] = size_bytes
        return allocated_sizes

    def teardown_indexes(self, indexes: List[HypoIndex]) -> None:
        """Drops physical indexes from the live database."""
        for idx in indexes:
            self.connector.drop_index(idx.name)

    def extract_used_indexes_from_plan(self, plan_rows: List[Tuple]) -> List[str]:
        """Extracts index names referenced in SQLite EXPLAIN QUERY PLAN detail strings."""
        used: List[str] = []
        for row in plan_rows:
            detail = str(row[3]) if len(row) > 3 else ""
            matches = re.findall(r"USING\s+(?:COVERING\s+)?INDEX\s+([a-zA-Z0-9_]+)", detail, re.IGNORECASE)
            for m in matches:
                # Exclude SQLite internal primary key autoindexes
                if m not in used and not m.startswith("sqlite_autoindex_"):
                    used.append(m)
        return used

    def verify_and_tune(
        self,
        workload: List[WorkloadQuery],
        initial_candidates: List[HypoIndex],
        storage_budget_bytes: int,
        mcts_iterations: int = 300
    ) -> VerificationResult:
        """Executes full Stage 2 MCTS + Stage 3 physical verification with ReAct regression reflection."""
        # Ensure clean state before benchmarking
        self.tabu_list.clear()
        try:
            cur_indexes = [
                row[0] for row in self.connector.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_autoindex_%';"
                )
            ]
            for idx_name in cur_indexes:
                self.connector.drop_index(idx_name)
        except Exception:
            pass

        # Step 0: Untimed cache warm-up to prevent cold-cache measurement skew
        for q in workload:
            try:
                self.connector.execute(q.sql)
            except Exception:
                pass

        # Step 1: Benchmark unindexed baseline
        base_times: Dict[str, float] = {}
        base_plans: Dict[str, List[Tuple]] = {}
        for q in workload:
            t_ms, plan = self.benchmark_query(q)
            base_times[q.query_id] = t_ms
            base_plans[q.query_id] = plan

        total_base_weighted_ms = sum(base_times[q.query_id] * q.weight for q in workload)

        # Step 2: ReAct Optimization & Reflection Loop
        cycle = 0
        best_active_indexes: List[HypoIndex] = []
        last_mcts_res: Optional[MCTSResult] = None
        query_results: Dict[str, QueryBenchmarkResult] = {}
        regressions_detected: List[str] = []

        while cycle <= self.max_reflection_cycles:
            # Filter out tabu indexes
            active_candidates = [
                idx for idx in initial_candidates
                if idx.name not in self.tabu_list and idx.key not in self.tabu_list
            ]

            # Solve via MCTS
            solver = MCTSSolver(
                cost_engine=self.cost_engine,
                candidate_pool=active_candidates,
                storage_budget_bytes=storage_budget_bytes,
                iterations=mcts_iterations
            )
            mcts_res = solver.solve(workload)
            last_mcts_res = mcts_res
            best_active_indexes = mcts_res.best_indexes

            # If no indexes selected, break early
            if not best_active_indexes:
                break

            # Materialize indexes physically on live database
            allocated_sizes = self.materialize_indexes(best_active_indexes)

            # Benchmark optimized workload
            opt_times: Dict[str, float] = {}
            opt_plans: Dict[str, List[Tuple]] = {}
            query_results.clear()
            regressions_detected.clear()

            for q in workload:
                t_ms, plan = self.benchmark_query(q)
                opt_times[q.query_id] = t_ms
                opt_plans[q.query_id] = plan

                b_time = base_times[q.query_id]
                used_idxs = self.extract_used_indexes_from_plan(plan)
                speedup = (b_time / t_ms) if t_ms > 0 else 1.0

                # Regression Check: wall-clock time regressed by more than threshold
                # Requires that the query actually utilized an index materialized in this cycle
                active_names = {idx.name for idx in best_active_indexes}
                used_active_idxs = [idx for idx in used_idxs if idx in active_names]
                is_regressed = (
                    bool(used_active_idxs) and
                    (t_ms > (1.0 + self.regression_threshold) * b_time) and
                    (t_ms - b_time > 2.0)
                )

                if is_regressed:
                    regressions_detected.append(q.query_id)


                query_results[q.query_id] = QueryBenchmarkResult(
                    query_id=q.query_id,
                    base_time_ms=b_time,
                    opt_time_ms=t_ms,
                    speedup_ratio=speedup,
                    base_plan_raw=base_plans[q.query_id],
                    opt_plan_raw=plan,
                    used_indexes=used_idxs,
                    has_regressed=is_regressed
                )

            # Check if regressions occurred or workload overall regressed
            curr_opt_weighted_ms = sum(
                query_results[q.query_id].opt_time_ms * q.weight
                for q in workload
            ) if query_results else total_base_weighted_ms

            # ReAct Reflection Check: trigger tabu backtracking if specific queries regressed
            if regressions_detected and cycle < self.max_reflection_cycles:
                # Identify culprit index from regressed queries
                culprit_found = False
                for reg_qid in regressions_detected:
                    reg_used = query_results[reg_qid].used_indexes
                    for u_idx in reg_used:
                        if u_idx not in self.tabu_list:
                            self.tabu_list.add(u_idx)
                            culprit_found = True
                            break
                    if culprit_found:
                        break

                if culprit_found:
                    # Teardown current indexes before re-solving
                    self.teardown_indexes(best_active_indexes)
                    cycle += 1
                    continue
                else:
                    break
            else:
                # No regressions or reached max reflection cycles: accept configuration
                break

        # Step 3: Compute final metrics
        total_opt_weighted_ms = sum(
            query_results[q.query_id].opt_time_ms * q.weight
            for q in workload
        ) if query_results else total_base_weighted_ms

        # Final safety check: if the final configuration is slower than or equal to baseline,
        # roll back physical indexes to ensure zero performance regression in production.
        if total_opt_weighted_ms >= total_base_weighted_ms:
            self.teardown_indexes(best_active_indexes)
            best_active_indexes = []
            total_opt_weighted_ms = total_base_weighted_ms
            workload_speedup = 1.0
            total_storage_bytes = 0
            for q in workload:
                if q.query_id in query_results:
                    qr = query_results[q.query_id]
                    qr.opt_time_ms = qr.base_time_ms
                    qr.speedup_ratio = 1.0
                    qr.used_indexes = []
                    qr.has_regressed = False
        else:
            workload_speedup = (
                (total_base_weighted_ms / total_opt_weighted_ms)
                if total_opt_weighted_ms > 0 else 1.0
            )
            total_storage_bytes = sum(
                self.connector.get_index_size_bytes(idx.name)
                for idx in best_active_indexes
            )

        budget_ok = total_storage_bytes <= storage_budget_bytes

        return VerificationResult(
            workload_speedup=workload_speedup,
            total_base_time_ms=total_base_weighted_ms,
            total_opt_time_ms=total_opt_weighted_ms,
            storage_used_bytes=total_storage_bytes,
            storage_budget_bytes=storage_budget_bytes,
            budget_compliant=budget_ok,
            query_results=query_results,
            regressions_detected=regressions_detected,
            reflection_cycles=cycle,
            active_indexes=best_active_indexes,
            mcts_result=last_mcts_res
        )

