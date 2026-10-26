# PLAN.md: Step-by-Step Implementation Plan for Project 4

**Project:** AutoTune-DB - Hierarchical Hybrid Autonomous Agent for Physical Database Design  
**Spec Reference:** [SPEC.md](file:///c:/Users/aksha/DSAI_Projects/Project4_AutoTune_DB/SPEC.md)  
**Methodology:** Spec-Driven Development (SDD) - Chapter 13  
**Target Grade:** A+ (Flawless systems deployment, 4-way ablation, rigorous viva defense)  

---

## Phase 1: Database Engine Layer, TPC-H Schema & Workload Harness

- [x] **Task 1.1: Directory Scaffolding & Component Verification**
  - Verify project subdirectories:
    - `src/engine/`, `src/miner/`, `src/mcts/`, `src/agent/`, `src/benchmark/`
    - `tests/`, `app/`, `data/tpch_data/`
  - Verify Python runtime and standard library dependencies (`sqlite3`, `pandas`, `numpy`, `pytest`, `streamlit`, `plotly`).

- [x] **Task 1.2: Abstract Database Connector & Local Engine (`src/engine/db_connector.py`)**
  - Implement abstract `DatabaseConnector` interface (`execute`, `explain`, `create_index`, `drop_index`, `get_index_size_bytes`, `get_table_cardinality`).
  - Implement `SQLiteConnector` supporting low-level execution plan inspection (`EXPLAIN QUERY PLAN`), page allocations, and index byte sizes via `dbstat` / physical page tracking.
  - Provide extensible hook for `DuckDBConnector`.

- [x] **Task 1.3: Standard TPC-H 8-Table Schema & Synthetic Data Generator (`src/engine/tpch_schema.py`)**
  - Define full relational DDL for TPC-H tables:
    `region`, `nation`, `supplier`, `customer`, `part`, `partsupp`, `orders`, `lineitem`.
  - Implement synthetic data populator with configurable scale factors (SF=0.01 to SF=0.1 for fast unit testing, up to SF=1.0 for final benchmarking).
  - Enforce foreign key constraints and primary key indexes.

- [x] **Task 1.4: TPC-H Analytical Query Suite (`src/engine/tpch_workload.py`)**
  - Curate a representative analytical workload spanning major TPC-H query patterns:
    - **Q1 (Pricing Summary Report):** Heavy range filter on `l_shipdate`, multi-attribute aggregation.
    - **Q3 (Shipping Priority):** Multi-table join (`customer` $\bowtie$ `orders` $\bowtie$ `lineitem`) with date filters and top-$K$ ordering.
    - **Q6 (Forecasting Revenue Change):** Multi-attribute conjunction on `(l_shipdate, l_discount, l_quantity)`.
    - **Q10 (Returned Item Reporting):** Complex join with grouping across 4 tables.
    - **Q12 (Shipping Modes & Order Priority):** Join on `lineitem` and `orders` with receipt date range filters.
  - Structure workload with query weights $w_i$.

- [x] **Task 1.5: Unit Tests for Database Engine & Workload Execution (`tests/test_engine.py`)**
  - Test database population, query execution, and measurement of baseline execution times.
  - **Acceptance Gate 1:** `pytest tests/test_engine.py` passes 100% (6/6 tests passed).

---

## Phase 2: Physical Plan AST Parser & Hypothetical Cost Engine

- [x] **Task 2.1: Execution Plan AST Parser (`src/engine/plan_parser.py`)**
  - Parse engine execution plans into recursive, strongly typed `PlanNode` trees.
  - Distinguish physical relational operators:
    - `SeqScanNode` (SCAN TABLE)
    - `IndexScanNode` (SEARCH TABLE USING INDEX)
    - `CoveringIndexScanNode` (SEARCH TABLE USING COVERING INDEX)
    - `TempBTreeSortNode` (USE TEMP B-TREE FOR ORDER BY/GROUP BY)
    - `HashJoinNode` / `NestedLoopJoinNode`

- [x] **Task 2.2: Bottleneck Operator Attribution & Isolation**
  - Traverse the `PlanNode` tree to compute per-operator cost attribution.
  - Isolate bottleneck leaf operators responsible for $\ge 30\%$ of individual query runtime and $\ge 70\%$ of cumulative workload latency.
  - Extract target table names and predicate column references for each bottleneck.

- [x] **Task 2.3: Zero-Byte Hypothetical Cost Engine (`src/engine/hypo_cost_engine.py`)**
  - Implement sub-millisecond query cost estimation under hypothetical index configurations $\mathcal{I}_{\text{hypo}}$ without writing physical index pages to disk.
  - Implement the B-Tree cost model accounting for fanout, tree height $h = \lceil \log_B(N) \rceil$, and the selectivity crossover point $\sigma^*$.
  - Return estimated cost vector across all workload queries $\mathcal{W}$.

- [x] **Task 2.4: Unit Tests for Plan AST Parser & Cost Modeling (`tests/test_plan_parser.py`, `tests/test_hypo_cost_engine.py`)**
  - Verify recursive plan node tree construction and bottleneck identification.
  - Verify that adding a matching hypothetical index reduces estimated query cost, while an irrelevant index yields identical cost.
  - **Acceptance Gate 2:** `pytest tests/test_plan_parser.py tests/test_hypo_cost_engine.py` passes 100% (10/10 tests passed).

---

## Phase 3: Stage 1 - AST Semantic Predicate Miner & Candidate Pool Generator

- [x] **Task 3.1: SQL AST Visitor & Predicate Extractor (`src/miner/ast_visitor.py`)**
  - Parse SQL queries using Python AST / regex visitor to extract:
    - Referenced table names.
    - `WHERE` clause filter predicates (`=`, `<`, `>`, `<=`, `>=`, `BETWEEN`, `IN`).
    - `JOIN ON` foreign-key linkages.
    - `GROUP BY` and `ORDER BY` column tuples.

- [x] **Task 3.2: Leftmost Prefix Rule & Equality-First Ordering (`src/miner/candidate_miner.py`)**
  - Implement the relational B-Tree ordering algorithm:
    1. Equality predicates ($C_{\text{eq}} = v$) are placed in leading positions.
    2. Range predicates ($C_{\text{range}} \ge v_1$) are placed after equality columns.
  - Sort equality columns by descending cardinality/selectivity.

- [x] **Task 3.3: Prefix Sharing & Action Space Pruning**
  - Detect prefix containment: if Candidate $A = (T, [x])$ is a strict prefix of Candidate $B = (T, [x, y])$, merge them into $B$ to eliminate redundant storage allocation.
  - Filter out low-cardinality attributes ($\sigma < \tau_{\text{thresh}}$) to prevent unclustered random I/O thrashing.
  - Bounded candidate pool generation: compress $>3,500$ blind index permutations down to $|\mathcal{C}| \in [30, 50]$ high-value candidate single and composite indexes.

- [x] **Task 3.4: Unit Tests for Candidate Mining (`tests/test_candidate_miner.py`)**
  - Test predicate extraction on all TPC-H workload queries.
  - Verify that candidate pool size strictly satisfies $30 \le |\mathcal{C}| \le 50$.
  - Verify Equality-First ordering on composite candidates.
  - **Acceptance Gate 3:** `pytest tests/test_candidate_miner.py` passes 100% (6/6 tests passed).

---

## Phase 4: Stage 2 - MCTS Combinatorial Solver with UCT Policy

- [x] **Task 4.1: MCTS Tree Node Contract & State Representation (`src/mcts/node.py`)**
  - Implement `MCTSNode` dataclass tracking:
    - `state_indexes`: `FrozenSet[IndexCandidate]`
    - `cumulative_size_bytes`: Total physical storage of active configuration
    - `visits`: $N(s)$
    - `total_reward`: Accumulated reward
    - `q_value`: $Q(s) = \text{total\_reward} / \text{visits}$
    - `children`: Dict mapping candidate index addition to child `MCTSNode`

- [x] **Task 4.2: Upper Confidence Bound for Trees (UCT) Selection Policy (`src/mcts/uct_policy.py`)**
  - Implement standard UCT formula balancing exploitation and exploration:
    $$\text{UCT}(s, a) = Q(s, a) + c \cdot \sqrt{\frac{\ln N(s)}{N(s, a)}}$$
    with exploration constant $c = \sqrt{2} \approx 1.414$.

- [x] **Task 4.3: Budget-Constrained Rollout & Penalty Reward Engine (`src/mcts/mcts_solver.py`)**
  - Implement rollout policy evaluating candidate additions via `HypoCostEngine`.
  - Formulate reward function strictly penalizing hard budget violations:
    $$\mathcal{R}(s) = \frac{\text{Cost}_{\text{base}}(\mathcal{W}) - \text{Cost}(s, \mathcal{W})}{\text{Cost}_{\text{base}}(\mathcal{W})} - \lambda \cdot \max(0, \text{Size}(s) - B)$$
  - Implement search loop with configurable rollout budget (e.g., 500 iterations).
  - Extract optimal configuration $\mathcal{I}^* = \arg\max_s Q(s)$ subject to $\text{Size}(\mathcal{I}^*) \le B$.

- [x] **Task 4.4: Dynamic Programming 0-1 Knapsack Baseline Comparison**
  - Implement standard 0-1 Knapsack / greedy benefit-to-size baseline comparison method on `MCTSSolver`.

- [x] **Task 4.5: Unit Tests for MCTS Solver (`tests/test_mcts_solver.py`)**
  - Test UCT selection, expansion, and backpropagation.
  - Verify Storage Budget Invariant: returned index set never exceeds $B$ (100% compliance across diverse budgets).
  - Verify monotonic speedup ($>1.0$) and sub-1.5s search latency (500 rollouts completed in ~0.75s).
  - **Acceptance Gate 4:** `pytest tests/test_mcts_solver.py` passes 100% (7/7 tests passed).


---

## Phase 5: Stage 3 - Live DB Verification, LLM Reflection & 4-Way Ablation Benchmark

- [x] **Task 5.1: Live Physical Index Materialization & Benchmark Runner (`src/agent/react_controller.py`)**
  - Take the MCTS winning configuration $\mathcal{I}^*$ and physically construct indexes on the live database.
  - Measure exact physical index bytes via page allocations and catalog tracking.
  - Execute workload queries $\mathcal{W}$ and record actual wall-clock latencies (median across repeat runs).

- [x] **Task 5.2: Cost-Based Optimizer (CBO) Plan Regression Detector & Tabu Backtracking**
  - Detect optimizer plan regressions (queries where wall-clock latency increased despite index creation).
  - Implement self-correcting reflection routine: drop offending indexes, add them to tabu list, and trigger localized MCTS re-search.

- [x] **Task 5.3: Automated DBA Physical Design Dossier Generator (`src/agent/dossier_generator.py`)**
  - Generate a formal Markdown audit report detailing:
    - Speedup per query and overall workload speedup.
    - Plan tree deltas (Sequential Scans converted to Index Scans).
    - Storage budget utilization breakdown.
    - Production DDL statements ready for deployment.

- [x] **Task 5.4: 4-Way Controlled Ablation Benchmark (`src/benchmark/ablation_runner.py`)**
  - Execute end-to-end comparative benchmark across:
    1. **Ablation 1:** Unindexed Baseline (Primary Keys only).
    2. **Ablation 2:** Pure Heuristic / LLM Selection (frequency-based greedy heuristics).
    3. **Ablation 3:** Pure MCTS Agent (Combinatorial search over naive unpruned space).
    4. **Ablation 4:** AutoTune-DB (Winning Hybrid: AST Miner $\to$ MCTS Solver $\to$ Live Verifier).
  - Comparative metrics table and Markdown summary formatter.

- [x] **Task 5.5: End-to-End Hybrid Test Suite (`tests/test_end_to_end_hybrid.py`)**
  - Run full 3-stage pipeline end-to-end on populated TPC-H instance.
  - Verify $\text{Speedup} > 1.0$, $\text{Size} \le B$, and valid DBA dossier generation.
  - **Acceptance Gate 5:** `pytest tests/test_end_to_end_hybrid.py` passes 100% (5/5 tests passed).


---

## Phase 6: Interactive Streamlit Dashboard & Viva Defense Readiness

- [x] **Task 6.1: Interactive Streamlit Dashboard (`app/streamlit_app.py`)**
  - Visual components:
    1. **MCTS Search Tree Visualizer:** Live interactive tree plot (via Plotly) showing node visits, Q-values, and pruning paths.
    2. **Execution Plan Delta Viewer:** Side-by-side execution plan trees showing operator transitions.
    3. **Storage Budget Gauge:** Real-time gauge showing budget $B$ packing.
    4. **Ablation Arena:** Bar charts comparing the 4-way ablation configurations.

- [x] **Task 6.2: Walkthrough Documentation & Viva Defense Guide (`WALKTHROUGH.md`)**
  - Compile the complete technical walkthrough with whiteboard mathematical derivations:
    - ISP NP-Hardness reduction proof.
    - UCT exploration-exploitation bound from Hoeffding's inequality.
    - B-Tree selectivity crossover threshold ($\sigma^*$).
    - Neuro-symbolic hybrid agent justification.
  - **Final Acceptance Gate:** All 34 unit and integration tests pass (100%), Streamlit app compiles and runs cleanly, and `WALKTHROUGH.md` is complete.

