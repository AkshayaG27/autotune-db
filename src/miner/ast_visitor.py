"""SQL AST Visitor & Relational Predicate Extractor.

Parses SQL query text to extract referenced tables, filter predicates (equality, range, set),
join equi-predicates, and grouping/sorting attributes.
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional


class PredicateOp(Enum):
    EQUALITY = "EQUALITY"       # =
    RANGE = "RANGE"             # <, >, <=, >=, BETWEEN
    SET = "SET"                 # IN (...)
    JOIN = "JOIN"               # tableA.col1 = tableB.col2


@dataclass(frozen=True)
class ColumnPredicate:
    table: str
    column: str
    op_type: PredicateOp
    raw_expression: str

    @property
    def key(self) -> str:
        return f"{self.table.lower()}.{self.column.lower()}"


@dataclass
class QueryPredicateSummary:
    query_id: str
    tables: Set[str] = field(default_factory=set)
    filter_predicates: List[ColumnPredicate] = field(default_factory=list)
    join_predicates: List[ColumnPredicate] = field(default_factory=list)
    group_by_columns: Dict[str, List[str]] = field(default_factory=dict)
    order_by_columns: Dict[str, List[str]] = field(default_factory=dict)

    def get_columns_for_table(self, table: str) -> List[str]:
        """Returns all referenced filter and join columns for a table in this query."""
        t_lower = table.lower()
        cols = []
        for p in self.filter_predicates + self.join_predicates:
            if p.table.lower() == t_lower and p.column.lower() not in cols:
                cols.append(p.column.lower())
        return cols


class SQLPredicateVisitor:
    """Parses SQL queries into structured QueryPredicateSummary objects."""

    # TPC-H column prefix mapping to table
    PREFIX_TABLE_MAP: Dict[str, str] = {
        "l_": "lineitem",
        "o_": "orders",
        "c_": "customer",
        "p_": "part",
        "ps_": "partsupp",
        "s_": "supplier",
        "n_": "nation",
        "r_": "region"
    }

    KNOWN_TABLES = set(PREFIX_TABLE_MAP.values())

    @classmethod
    def resolve_table_for_column(cls, col_name: str, candidate_tables: Optional[Set[str]] = None) -> Optional[str]:
        """Resolves table name for column based on standard TPC-H naming prefix."""
        col_lower = col_name.strip().lower()
        for prefix, table in cls.PREFIX_TABLE_MAP.items():
            if col_lower.startswith(prefix):
                return table
        # If candidate tables provided and length 1, attribute to that table
        if candidate_tables and len(candidate_tables) == 1:
            return list(candidate_tables)[0]
        return None

    @classmethod
    def extract_predicates(cls, sql: str, query_id: str = "") -> QueryPredicateSummary:
        """Parses a SQL query and returns its predicate and join summary."""
        summary = QueryPredicateSummary(query_id=query_id)
        sql_clean = re.sub(r"\s+", " ", sql).strip()

        # 1. Extract referenced tables from FROM clause
        from_match = re.search(r"\bFROM\s+(.+?)(?:\bWHERE\b|\bGROUP\b|\bORDER\b|\bLIMIT\b|$)", sql_clean, re.IGNORECASE)
        if from_match:
            from_clause = from_match.group(1)
            # Match table names
            for t in cls.KNOWN_TABLES:
                if re.search(rf"\b{t}\b", from_clause, re.IGNORECASE):
                    summary.tables.add(t)

        # 2. Extract WHERE clause predicates
        where_match = re.search(r"\bWHERE\s+(.+?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|$)", sql_clean, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)

            # First extract all BETWEEN clauses before splitting on AND
            between_pattern = re.compile(r"\b([a-zA-Z0-9_]+)\s+BETWEEN\s+(.+?)\s+AND\s+([^\s;,)]+)", re.IGNORECASE)
            for bm in between_pattern.finditer(where_clause):
                col = bm.group(1)
                table = cls.resolve_table_for_column(col, summary.tables)
                if table:
                    summary.filter_predicates.append(
                        ColumnPredicate(table, col.lower(), PredicateOp.RANGE, bm.group(0))
                    )
            # Remove matched BETWEEN clauses to avoid splitting on their internal AND
            where_no_between = between_pattern.sub(" ", where_clause)

            # Split remaining clauses on AND / OR
            clauses = re.split(r"\bAND\b|\bOR\b", where_no_between, flags=re.IGNORECASE)
            for clause in clauses:
                clause_str = clause.strip()
                if not clause_str:
                    continue
                cls._parse_where_clause(clause_str, summary)

        # 3. Extract GROUP BY columns
        group_match = re.search(r"\bGROUP\s+BY\s+(.+?)(?:\bORDER\b|\bLIMIT\b|$)", sql_clean, re.IGNORECASE)
        if group_match:
            group_cols = [c.strip() for c in group_match.group(1).split(",")]
            for col in group_cols:
                table = cls.resolve_table_for_column(col, summary.tables)
                if table:
                    summary.group_by_columns.setdefault(table, []).append(col.lower())

        # 4. Extract ORDER BY columns
        order_match = re.search(r"\bORDER\s+BY\s+(.+?)(?:\bLIMIT\b|$)", sql_clean, re.IGNORECASE)
        if order_match:
            order_cols = [c.strip().split()[0] for c in order_match.group(1).split(",")]
            for col in order_cols:
                table = cls.resolve_table_for_column(col, summary.tables)
                if table:
                    summary.order_by_columns.setdefault(table, []).append(col.lower())

        return summary

    @classmethod
    def _parse_where_clause(cls, clause: str, summary: QueryPredicateSummary) -> None:
        """Parses a single atomic predicate clause (e.g. 'c_mktsegment = BUILDING' or 'c_custkey = o_custkey')."""
        # A. Check for BETWEEN clause (Range)
        between_match = re.search(r"([a-zA-Z0-9_]+)\s+BETWEEN\s+(.+?)\s+AND\s+(.+)", clause, re.IGNORECASE)
        if between_match:
            col = between_match.group(1)
            table = cls.resolve_table_for_column(col, summary.tables)
            if table:
                summary.filter_predicates.append(
                    ColumnPredicate(table, col.lower(), PredicateOp.RANGE, clause)
                )
            return

        # B. Check for IN (...) clause (Set)
        in_match = re.search(r"([a-zA-Z0-9_]+)\s+IN\s*\((.+?)\)", clause, re.IGNORECASE)
        if in_match:
            col = in_match.group(1)
            table = cls.resolve_table_for_column(col, summary.tables)
            if table:
                summary.filter_predicates.append(
                    ColumnPredicate(table, col.lower(), PredicateOp.SET, clause)
                )
            return

        # C. Check for Inequality Range comparisons: <=, >=, <, >
        range_match = re.search(r"([a-zA-Z0-9_]+)\s*(<=|>=|<|>)\s*(.+)", clause)
        if range_match:
            col = range_match.group(1)
            table = cls.resolve_table_for_column(col, summary.tables)
            if table:
                summary.filter_predicates.append(
                    ColumnPredicate(table, col.lower(), PredicateOp.RANGE, clause)
                )
            return

        # D. Check for Equality or Join (=)
        eq_match = re.search(r"([a-zA-Z0-9_]+)\s*=\s*([a-zA-Z0-9_'\"]+)", clause)
        if eq_match:
            left_col = eq_match.group(1)
            right_val = eq_match.group(2).strip("'\"")

            left_table = cls.resolve_table_for_column(left_col, summary.tables)
            right_table = cls.resolve_table_for_column(right_val, summary.tables)

            # If both left and right resolve to known tables, this is a JOIN condition
            if left_table and right_table and left_table != right_table:
                summary.join_predicates.append(
                    ColumnPredicate(left_table, left_col.lower(), PredicateOp.JOIN, clause)
                )
                summary.join_predicates.append(
                    ColumnPredicate(right_table, right_val.lower(), PredicateOp.JOIN, clause)
                )
            elif left_table:
                # Regular filter equality (e.g. c_mktsegment = 'BUILDING')
                summary.filter_predicates.append(
                    ColumnPredicate(left_table, left_col.lower(), PredicateOp.EQUALITY, clause)
                )
            return
