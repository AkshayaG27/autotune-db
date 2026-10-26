"""Stage 1: AST Semantic Predicate Miner & Candidate Pool Generator.

Synthesizes a compact, high-value pool of candidate single and composite indexes (30 <= |C| <= 50)
by enforcing Leftmost Prefix Rules, Equality-First sorting, and prefix subsumption.
"""

from typing import List, Dict, Set, Tuple, Optional
from src.engine.db_connector import DatabaseConnector
from src.engine.tpch_workload import WorkloadQuery
from src.engine.hypo_cost_engine import HypoIndex
from src.miner.ast_visitor import SQLPredicateVisitor, PredicateOp, QueryPredicateSummary


class CandidateMiner:
    """Mines a bounded pool of candidate indexes from a SQL workload."""

    # Default empirical cardinalities for sorting equality attributes
    DEFAULT_CARDINALITY_ORDER: Dict[str, float] = {
        "l_orderkey": 0.95,
        "o_orderkey": 0.95,
        "o_custkey": 0.85,
        "c_custkey": 0.85,
        "l_partkey": 0.80,
        "l_suppkey": 0.75,
        "p_partkey": 0.80,
        "s_suppkey": 0.75,
        "l_discount": 0.50,
        "o_orderdate": 0.45,
        "l_receiptdate": 0.40,
        "l_commitdate": 0.35,
        "c_mktsegment": 0.20,
        "l_quantity": 0.18,
        "l_shipmode": 0.15,
        "l_shipdate": 0.10,
        "n_nationkey": 0.04,
        "l_returnflag": 0.03,
        "l_linestatus": 0.02
    }

    def __init__(self, connector: DatabaseConnector, min_pool_size: int = 30, max_pool_size: int = 50):
        self.connector = connector
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size

    def mine_candidates(self, workload: List[WorkloadQuery]) -> List[HypoIndex]:
        """Synthesizes high-value candidate pool C satisfying 30 <= |C| <= 50.
        
        Enforces:
        1. Equality-First ordering (equality and join predicates precede range predicates).
        2. Cardinality ordering for dual-equality predicates.
        3. Deduplication and bounded pool sizing.
        """
        # 1. Parse all workload queries
        summaries: List[QueryPredicateSummary] = [
            SQLPredicateVisitor.extract_predicates(q.sql, q.query_id)
            for q in workload
        ]

        # 2. Collect predicates and co-occurring columns per table
        # table -> set of single columns
        table_single_cols: Dict[str, Set[str]] = {}
        # table -> list of (co_occurring_columns, query_weight, query_id)
        table_query_contexts: Dict[str, List[Tuple[List[str], float, str]]] = {}
        # (table, column) -> PredicateOp
        col_op_types: Dict[Tuple[str, str], PredicateOp] = {}

        for summary in summaries:
            q_query = next((q for q in workload if q.query_id == summary.query_id), None)
            weight = q_query.weight if q_query else 1.0

            # Register filter predicates
            for p in summary.filter_predicates:
                t = p.table.lower()
                c = p.column.lower()
                table_single_cols.setdefault(t, set()).add(c)
                col_op_types[(t, c)] = p.op_type

            # Register join predicates
            for p in summary.join_predicates:
                t = p.table.lower()
                c = p.column.lower()
                table_single_cols.setdefault(t, set()).add(c)
                col_op_types[(t, c)] = PredicateOp.JOIN

            # Group columns by table for this query
            for t in summary.tables:
                t_lower = t.lower()
                cols = summary.get_columns_for_table(t_lower)
                if cols:
                    table_query_contexts.setdefault(t_lower, []).append((cols, weight, summary.query_id))

        candidate_set: Dict[Tuple[str, Tuple[str, ...]], float] = {}

        # 3. Formulate Single-Column Candidates
        for t, cols in table_single_cols.items():
            for c in cols:
                # Score based on queries referencing this column
                score = 15.0
                for context_cols, w, _ in table_query_contexts.get(t, []):
                    if c in context_cols:
                        score += 8.0 * w
                op = col_op_types.get((t, c), PredicateOp.EQUALITY)
                if op == PredicateOp.JOIN:
                    score += 20.0
                candidate_set[(t, (c,))] = score

        # 4. Formulate 2-Column Composite Candidates with Equality-First Ordering
        for t, contexts in table_query_contexts.items():
            for cols, w, q_id in contexts:
                if len(cols) >= 2:
                    # Generate all pairs
                    for i in range(len(cols)):
                        for j in range(i + 1, len(cols)):
                            ordered_pair = self._order_columns_equality_first(t, [cols[i], cols[j]], col_op_types)
                            score = 25.0 * w
                            if any(col_op_types.get((t, col)) == PredicateOp.JOIN for col in ordered_pair):
                                score += 15.0 * w
                            elif any(col_op_types.get((t, col)) in (PredicateOp.SET, PredicateOp.EQUALITY) for col in ordered_pair):
                                score += 12.0 * w
                            candidate_set[(t, tuple(ordered_pair))] = max(
                                candidate_set.get((t, tuple(ordered_pair)), 0.0),
                                score
                            )

        # 5. Formulate 3-Column Composite Candidates (Conjunctions / Join-Filter combinations)
        for t, contexts in table_query_contexts.items():
            for cols, w, q_id in contexts:
                if len(cols) >= 3:
                    for i in range(len(cols)):
                        for j in range(i + 1, len(cols)):
                            for k in range(j + 1, len(cols)):
                                ordered_triplet = self._order_columns_equality_first(
                                    t, [cols[i], cols[j], cols[k]], col_op_types
                                )
                                score = 30.0 * w
                                if any(col_op_types.get((t, col)) == PredicateOp.JOIN for col in ordered_triplet):
                                    score += 15.0 * w
                                elif all(col_op_types.get((t, col)) in (PredicateOp.RANGE, PredicateOp.EQUALITY, PredicateOp.SET) for col in ordered_triplet):
                                    score += 18.0 * w
                                candidate_set[(t, tuple(ordered_triplet))] = max(
                                    candidate_set.get((t, tuple(ordered_triplet)), 0.0),
                                    score
                                )

        # 6. Filter out redundant primary key indexes (relational engines already maintain unique primary key indexes)
        primary_keys = {
            "orders": "o_orderkey",
            "customer": "c_custkey",
            "supplier": "s_suppkey",
            "part": "p_partkey",
            "nation": "n_nationkey",
            "region": "r_regionkey"
        }
        for (t, cols) in list(candidate_set.keys()):
            pk = primary_keys.get(t)
            # Single-column primary keys are already uniquely indexed by SQLite
            if pk and cols == (pk,):
                candidate_set.pop((t, cols), None)
                continue
            # If the primary key is leading, an index is redundant because the primary key auto-index already covers it
            # Reorder composite candidates so secondary filter/join column leads
            if pk and cols[0] == pk:
                score = candidate_set.pop((t, cols))
                if len(cols) > 1:
                    reordered = tuple(c for c in cols if c != pk) + (pk,)
                    candidate_set[(t, reordered)] = max(candidate_set.get((t, reordered), 0.0), score)

        # 7. Ensure Pool Size reaches at least min_pool_size (30) by augmenting secondary permutations

        if len(candidate_set) < self.min_pool_size:
            self._augment_candidates(candidate_set, table_query_contexts, col_op_types)

        # 8. Sort candidates by relevance score descending with cross-table diversity
        by_table: Dict[str, List[Tuple[Tuple[str, Tuple[str, ...]], float]]] = {}
        for item in sorted(candidate_set.items(), key=lambda x: x[1], reverse=True):
            t = item[0][0]
            by_table.setdefault(t, []).append(item)

        table_order = ["orders", "customer", "lineitem", "nation", "partsupp", "part", "supplier", "region"]
        balanced_candidates: List[Tuple[Tuple[str, Tuple[str, ...]], float]] = []
        while any(by_table.values()):
            for t in table_order:
                if t in by_table and by_table[t]:
                    balanced_candidates.append(by_table[t].pop(0))
            for t in list(by_table.keys()):
                if t not in table_order and by_table[t]:
                    balanced_candidates.append(by_table[t].pop(0))

        # 9. Truncate to max_pool_size (50)
        bounded_candidates = balanced_candidates[:self.max_pool_size]

        # 10. Convert to HypoIndex objects

        hypo_pool: List[HypoIndex] = []
        for (table, cols), _ in bounded_candidates:
            cols_clean = "_".join(cols)
            idx_name = f"idx_{table}_{cols_clean}"
            hypo_pool.append(HypoIndex(table=table, columns=cols, name=idx_name))

        return hypo_pool

    def _order_columns_equality_first(
        self,
        table: str,
        columns: List[str],
        col_op_types: Dict[Tuple[str, str], PredicateOp]
    ) -> List[str]:
        """Orders columns so that Equality/Join columns strictly precede Range columns.
        
        Within equality columns, sorts by descending cardinality.
        """
        equality_cols = []
        range_cols = []

        for c in columns:
            op = col_op_types.get((table, c), PredicateOp.EQUALITY)
            if op in (PredicateOp.EQUALITY, PredicateOp.JOIN, PredicateOp.SET):
                equality_cols.append(c)
            else:
                range_cols.append(c)

        # Sort equality columns by descending cardinality
        equality_cols.sort(
            key=lambda c: self.DEFAULT_CARDINALITY_ORDER.get(c, 0.1),
            reverse=True
        )

        # Sort range columns by descending cardinality
        range_cols.sort(
            key=lambda c: self.DEFAULT_CARDINALITY_ORDER.get(c, 0.1),
            reverse=True
        )

        return equality_cols + range_cols

    def _augment_candidates(
        self,
        candidate_set: Dict[Tuple[str, Tuple[str, ...]], float],
        table_query_contexts: Dict[str, List[Tuple[List[str], float, str]]],
        col_op_types: Dict[Tuple[str, str], PredicateOp]
    ) -> None:
        """Adds secondary index variations if initial pool is smaller than min_pool_size."""
        # Add reverse orderings for dual equality pairs (useful for differing query access paths)
        new_items = {}
        for (t, cols), score in list(candidate_set.items()):
            if len(cols) == 2:
                c1, c2 = cols
                op1 = col_op_types.get((t, c1), PredicateOp.EQUALITY)
                op2 = col_op_types.get((t, c2), PredicateOp.EQUALITY)
                # If both are equality, reversed index is also a valid candidate
                if op1 in (PredicateOp.EQUALITY, PredicateOp.JOIN) and op2 in (PredicateOp.EQUALITY, PredicateOp.JOIN):
                    reversed_tuple = (c2, c1)
                    if (t, reversed_tuple) not in candidate_set:
                        new_items[(t, reversed_tuple)] = score * 0.85

            if len(candidate_set) + len(new_items) >= self.min_pool_size:
                break

        candidate_set.update(new_items)

        # If still under minimum, add key join attributes on foreign relations
        if len(candidate_set) < self.min_pool_size:
            supplemental_keys = [
                ("orders", ("o_orderdate",)),
                ("orders", ("o_custkey", "o_orderdate")),
                ("lineitem", ("l_shipdate",)),
                ("lineitem", ("l_receiptdate",)),
                ("lineitem", ("l_commitdate",)),
                ("customer", ("c_mktsegment",)),
                ("customer", ("c_mktsegment", "c_custkey")),
                ("lineitem", ("l_orderkey", "l_shipmode")),
                ("lineitem", ("l_partkey", "l_suppkey")),
                ("partsupp", ("ps_partkey", "ps_availqty")),
                ("partsupp", ("ps_suppkey", "ps_supplycost")),
                ("supplier", ("s_nationkey", "s_acctbal")),
                ("nation", ("n_regionkey", "n_name")),
            ]
            for t, cols in supplemental_keys:
                if (t, cols) not in candidate_set:
                    candidate_set[(t, cols)] = 15.0
                if len(candidate_set) >= self.min_pool_size:
                    break
