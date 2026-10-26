"""Stage 2: Budget-Constrained Monte Carlo Tree Search (MCTS) Combinatorial Solver.

Searches the 2^|C| index combination space over the zero-byte HypoCostEngine
under strict storage budget B, balancing exploitation and exploration via UCT.
"""

import time
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, FrozenSet
from src.engine.hypo_cost_engine import HypoCostEngine, HypoIndex
from src.engine.tpch_workload import WorkloadQuery
from src.mcts.node import MCTSNode
from src.mcts.uct_policy import UCTPolicy


@dataclass
class MCTSResult:
    """Encapsulates the winning physical index design and search metrics."""
    best_indexes: List[HypoIndex]
    best_cost: float
    base_cost: float
    speedup_ratio: float
    storage_used_bytes: int
    storage_budget_bytes: int
    budget_utilized_percent: float
    iterations_completed: int
    search_time_ms: float

    @property
    def cost_reduction_percent(self) -> float:
        """Percentage reduction in estimated workload cost."""
        if self.base_cost <= 0.0:
            return 0.0
        return max(0.0, (self.base_cost - self.best_cost) / self.base_cost * 100.0)

    @property
    def index_names(self) -> List[str]:
        """Names of recommended physical indexes."""
        return [idx.name for idx in self.best_indexes]


class MCTSSolver:
    """Combinatorial index optimizer utilizing Monte Carlo Tree Search with UCT."""

    def __init__(
        self,
        cost_engine: HypoCostEngine,
        candidate_pool: List[HypoIndex],
        storage_budget_bytes: int,
        c_param: float = 1.414,
        iterations: int = 500,
        penalty_lambda: float = 100.0
    ):
        self.cost_engine = cost_engine
        self.storage_budget_bytes = storage_budget_bytes
        self.c_param = c_param
        self.iterations = iterations
        self.penalty_lambda = penalty_lambda

        # Deduplicate candidate pool while preserving order
        unique_pool: List[HypoIndex] = []
        seen_keys: Set[str] = set()
        for idx in candidate_pool:
            if idx.key not in seen_keys:
                seen_keys.add(idx.key)
                unique_pool.append(idx)
        self.candidate_pool = unique_pool

        # Precompute index sizes and candidate indices for O(1) lookups during search
        self._index_sizes: Dict[HypoIndex, int] = {
            idx: self.cost_engine.estimate_index_size(idx)
            for idx in self.candidate_pool
        }
        self._candidate_order: Dict[HypoIndex, int] = {
            idx: i for i, idx in enumerate(self.candidate_pool)
        }

    def solve(self, workload: List[WorkloadQuery]) -> MCTSResult:
        """Executes MCTS tree search and returns the Pareto-optimal index configuration.
        
        Args:
            workload: List of weighted workload queries.
            
        Returns:
            MCTSResult containing best index set, speedup, and storage statistics.
        """
        start_time = time.perf_counter()

        # 1. Base Workload Cost (empty index set)
        base_cost = self.cost_engine.estimate_workload_cost(workload, frozenset())

        # Handle empty candidate pool or zero budget
        if not self.candidate_pool or self.storage_budget_bytes <= 0:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return MCTSResult(
                best_indexes=[],
                best_cost=base_cost,
                base_cost=base_cost,
                speedup_ratio=1.0,
                storage_used_bytes=0,
                storage_budget_bytes=self.storage_budget_bytes,
                budget_utilized_percent=0.0,
                iterations_completed=0,
                search_time_ms=elapsed_ms
            )

        # 2. Initialize Root Node (s0 = empty index set)
        root = MCTSNode(
            state_indexes=frozenset(),
            cumulative_size_bytes=0
        )
        # Untried actions for root: all candidates that fit within the total storage budget
        root.untried_actions = [
            idx for idx in self.candidate_pool
            if self._index_sizes.get(idx, 0) <= self.storage_budget_bytes
        ]

        best_indexes: FrozenSet[HypoIndex] = frozenset()
        best_cost: float = base_cost
        best_size: int = 0
        best_reward: float = 0.0

        # 3. MCTS Search Iterations
        for _ in range(self.iterations):
            curr = root

            # --- Phase A: Selection ---
            while curr.is_fully_expanded and not curr.is_leaf:
                _, curr = UCTPolicy.select_best_child(curr, c_param=self.c_param)

            # --- Phase B: Expansion ---
            eval_node: MCTSNode
            if not curr.is_fully_expanded:
                # Pop the most promising untried action (candidates pre-sorted by relevance)
                action = curr.untried_actions.pop(0)
                new_state = curr.state_indexes | {action}
                new_size = curr.cumulative_size_bytes + self._index_sizes.get(action, 0)

                # Canonical subset ordering: only allow subsequent candidates appearing AFTER action
                # Cap branching factor to top 8 candidates to permit deep traversal in bounded iterations
                action_idx = self._candidate_order.get(action, 0)
                child_untried = [
                    cand for cand in self.candidate_pool[action_idx + 1 :]
                    if new_size + self._index_sizes.get(cand, 0) <= self.storage_budget_bytes
                ][:8]

                child_node = MCTSNode(
                    state_indexes=new_state,
                    cumulative_size_bytes=new_size,
                    parent=curr,
                    action_from_parent=action,
                    untried_actions=child_untried
                )
                curr.add_child(action, child_node)
                eval_node = child_node
            else:
                # Terminal or leaf state (budget full or candidate space exhausted)
                eval_node = curr

            # --- Phase C: Monte Carlo Rollout Simulation & Evaluation ---
            sim_state = set(eval_node.state_indexes)
            sim_size = eval_node.cumulative_size_bytes
            sim_cost = self.cost_engine.estimate_workload_cost(workload, frozenset(sim_state))

            # Rollout simulation: greedily explore complementary candidates fitting storage budget
            rollout_candidates = (
                eval_node.untried_actions[:6] if eval_node.untried_actions
                else [c for c in self.candidate_pool if c not in sim_state][:6]
            )
            for cand in rollout_candidates:
                c_size = self._index_sizes.get(cand, 0)
                if sim_size + c_size <= self.storage_budget_bytes:
                    cand_cost = self.cost_engine.estimate_workload_cost(workload, frozenset(sim_state | {cand}))
                    if cand_cost < sim_cost:
                        sim_state.add(cand)
                        sim_size += c_size
                        sim_cost = cand_cost

            # Track global optimum subject to strict budget compliance
            if sim_cost < best_cost and sim_size <= self.storage_budget_bytes:
                best_cost = sim_cost
                best_indexes = frozenset(sim_state)
                best_size = sim_size

            # Compute budget-penalized reward: R(s) = PerfGain - lambda * (excess / B)
            perf_gain = (base_cost - sim_cost) / base_cost if base_cost > 0.0 else 0.0
            excess_bytes = max(0, sim_size - self.storage_budget_bytes)
            penalty = (self.penalty_lambda * (excess_bytes / max(1, self.storage_budget_bytes)))
            reward = perf_gain - penalty

            # --- Phase D: Backpropagation ---
            back_ptr: Optional[MCTSNode] = eval_node
            while back_ptr is not None:
                back_ptr.update(reward)
                back_ptr = back_ptr.parent

        # 4. Result Packaging
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        speedup = (base_cost / best_cost) if best_cost > 0.0 else 1.0
        budget_pct = (best_size / self.storage_budget_bytes * 100.0) if self.storage_budget_bytes > 0 else 0.0

        return MCTSResult(
            best_indexes=list(best_indexes),
            best_cost=best_cost,
            base_cost=base_cost,
            speedup_ratio=speedup,
            storage_used_bytes=best_size,
            storage_budget_bytes=self.storage_budget_bytes,
            budget_utilized_percent=budget_pct,
            iterations_completed=self.iterations,
            search_time_ms=elapsed_ms
        )

    def solve_knapsack_baseline(self, workload: List[WorkloadQuery]) -> MCTSResult:
        """Solves index selection using a greedy 0-1 Knapsack benefit/cost heuristic.
        
        Used as a standard baseline to demonstrate MCTS superiority over independent
        greedy choices when cross-query and composite index interactions exist.
        """
        start_time = time.perf_counter()
        base_cost = self.cost_engine.estimate_workload_cost(workload, frozenset())

        if not self.candidate_pool or self.storage_budget_bytes <= 0:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return MCTSResult(
                best_indexes=[],
                best_cost=base_cost,
                base_cost=base_cost,
                speedup_ratio=1.0,
                storage_used_bytes=0,
                storage_budget_bytes=self.storage_budget_bytes,
                budget_utilized_percent=0.0,
                iterations_completed=0,
                search_time_ms=elapsed_ms
            )

        # 1. Compute marginal benefit of each candidate in isolation
        candidate_efficiencies = []
        for idx in self.candidate_pool:
            size = self._index_sizes.get(idx, 4096)
            if size <= self.storage_budget_bytes:
                cost_with_idx = self.cost_engine.estimate_workload_cost(workload, frozenset([idx]))
                cost_reduction = max(0.0, base_cost - cost_with_idx)
                efficiency = cost_reduction / max(1, size)
                candidate_efficiencies.append((idx, size, cost_reduction, efficiency))

        # 2. Sort by benefit/size ratio descending
        candidate_efficiencies.sort(key=lambda item: item[3], reverse=True)

        # 3. Greedily pack until budget exhausted
        chosen: List[HypoIndex] = []
        current_size = 0
        for idx, size, _, _ in candidate_efficiencies:
            if current_size + size <= self.storage_budget_bytes:
                chosen.append(idx)
                current_size += size

        final_cost = self.cost_engine.estimate_workload_cost(workload, frozenset(chosen))
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        speedup = (base_cost / final_cost) if final_cost > 0.0 else 1.0
        budget_pct = (current_size / self.storage_budget_bytes * 100.0) if self.storage_budget_bytes > 0 else 0.0

        return MCTSResult(
            best_indexes=chosen,
            best_cost=final_cost,
            base_cost=base_cost,
            speedup_ratio=speedup,
            storage_used_bytes=current_size,
            storage_budget_bytes=self.storage_budget_bytes,
            budget_utilized_percent=budget_pct,
            iterations_completed=len(candidate_efficiencies),
            search_time_ms=elapsed_ms
        )
