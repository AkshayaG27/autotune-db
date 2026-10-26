"""Physical Query Plan AST Parser & Bottleneck Extractor.

Parses raw database EXPLAIN QUERY PLAN rows into a typed, hierarchical PlanNode AST,
attributes execution costs, and identifies primary bottleneck operators.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any


@dataclass
class PlanNode:
    """Represents a physical relational algebra operator in an execution plan AST."""
    node_id: int
    parent_id: int
    operator_type: str        # 'SCAN', 'INDEX_SCAN', 'COVERING_INDEX_SCAN', 'SORT', 'SUBQUERY', 'ROOT', 'OTHER'
    table_name: Optional[str] = None
    index_name: Optional[str] = None
    detail: str = ""
    is_bottleneck: bool = False
    estimated_cost: float = 0.0
    children: List['PlanNode'] = field(default_factory=list)

    def is_scan(self) -> bool:
        """Returns True if operator is a table or index scan."""
        return self.operator_type in ("SCAN", "INDEX_SCAN", "COVERING_INDEX_SCAN")

    def find_nodes_by_type(self, op_type: str) -> List['PlanNode']:
        """Recursively collects all descendant nodes matching op_type."""
        matches = []
        if self.operator_type == op_type:
            matches.append(self)
        for child in self.children:
            matches.extend(child.find_nodes_by_type(op_type))
        return matches

    def find_scans_by_table(self, table: str) -> List['PlanNode']:
        """Recursively collects scan nodes targeting a specific table."""
        matches = []
        if self.is_scan() and self.table_name and self.table_name.lower() == table.lower():
            matches.append(self)
        for child in self.children:
            matches.extend(child.find_scans_by_table(table))
        return matches


class PlanASTParser:
    """Parses raw execution plan rows into structured PlanNode trees."""

    SCAN_RE = re.compile(r"^SCAN\s+(?:TABLE\s+)?([a-zA-Z0-9_]+)", re.IGNORECASE)
    SEARCH_INDEX_RE = re.compile(
        r"^SEARCH\s+(?:TABLE\s+)?([a-zA-Z0-9_]+)\s+USING\s+(?:COVERING\s+)?INDEX\s+([a-zA-Z0-9_]+)",
        re.IGNORECASE
    )
    SEARCH_COVERING_RE = re.compile(r"USING\s+COVERING\s+INDEX", re.IGNORECASE)
    SEARCH_OTHER_RE = re.compile(r"^SEARCH\s+(?:TABLE\s+)?([a-zA-Z0-9_]+)", re.IGNORECASE)

    @classmethod
    def parse_sqlite_plan(
        cls,
        raw_rows: List[Tuple[int, int, int, str]],
        table_row_counts: Optional[Dict[str, int]] = None,
        bottleneck_row_threshold: int = 1000
    ) -> PlanNode:
        """Constructs a hierarchical PlanNode tree from SQLite EXPLAIN QUERY PLAN rows.
        
        Args:
            raw_rows: List of (id, parent, notused, detail) tuples.
            table_row_counts: Optional dict mapping table names to row counts for bottleneck tagging.
            bottleneck_row_threshold: Minimum row count for a SeqScan to be flagged as bottleneck.
            
        Returns:
            Root PlanNode of the execution plan tree.
        """
        table_counts = {k.lower(): v for k, v in (table_row_counts or {}).items()}
        node_map: Dict[int, PlanNode] = {}
        roots: List[PlanNode] = []

        # 1. First pass: Create PlanNode instances
        for row in raw_rows:
            node_id, parent_id, _, detail = row
            op_type, table_name, index_name = cls._classify_operator(detail)

            # Check if this node is a bottleneck
            is_bottleneck = False
            if op_type == "SCAN" and table_name:
                row_count = table_counts.get(table_name.lower(), 0)
                # If row count is unknown or exceeds threshold, flag as bottleneck
                if row_count >= bottleneck_row_threshold or not table_counts:
                    is_bottleneck = True

            node = PlanNode(
                node_id=node_id,
                parent_id=parent_id,
                operator_type=op_type,
                table_name=table_name,
                index_name=index_name,
                detail=detail,
                is_bottleneck=is_bottleneck
            )
            node_map[node_id] = node

        # 2. Second pass: Build parent-child relationships
        for node in node_map.values():
            if node.parent_id == 0 or node.parent_id not in node_map:
                roots.append(node)
            else:
                node_map[node.parent_id].children.append(node)

        # 3. If multiple root operators exist (e.g. subqueries, joins), wrap in synthetic ROOT
        if len(roots) == 1 and roots[0].node_id == 0:
            return roots[0]
        
        synthetic_root = PlanNode(
            node_id=0,
            parent_id=-1,
            operator_type="ROOT",
            detail="Query Execution Plan",
            children=roots
        )
        return synthetic_root

    @classmethod
    def _classify_operator(cls, detail: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Classifies operator type, table, and index from detail string."""
        detail_clean = detail.strip()

        # Check for Index Search (Covering or Standard)
        search_idx_match = cls.SEARCH_INDEX_RE.search(detail_clean)
        if search_idx_match:
            table = search_idx_match.group(1)
            index = search_idx_match.group(2)
            if cls.SEARCH_COVERING_RE.search(detail_clean):
                return "COVERING_INDEX_SCAN", table, index
            return "INDEX_SCAN", table, index

        # Check for other search (e.g. SEARCH TABLE USING INTEGER PRIMARY KEY)
        search_other_match = cls.SEARCH_OTHER_RE.search(detail_clean)
        if search_other_match:
            table = search_other_match.group(1)
            return "INDEX_SCAN", table, None

        # Check for Sequential Table Scan
        scan_match = cls.SCAN_RE.search(detail_clean)
        if scan_match:
            table = scan_match.group(1)
            return "SCAN", table, None

        # Check for Sorting / Temp B-Tree
        if detail_clean.upper().startswith("USE TEMP B-TREE"):
            return "SORT", None, None

        # Check for Subqueries / Compound operators
        if "SUBQUERY" in detail_clean.upper():
            return "SUBQUERY", None, None

        return "OTHER", None, None

    @classmethod
    def extract_bottlenecks(cls, root: PlanNode) -> List[PlanNode]:
        """Recursively traverses the tree and returns all nodes flagged as bottlenecks."""
        bottlenecks = []
        if root.is_bottleneck:
            bottlenecks.append(root)
        for child in root.children:
            bottlenecks.extend(cls.extract_bottlenecks(child))
        return bottlenecks

    @classmethod
    def format_ascii_tree(cls, root: PlanNode, prefix: str = "", is_last: bool = True) -> str:
        """Renders an ASCII tree representation of the execution plan."""
        lines = []
        marker = "\\-- " if is_last else "|-- "
        node_label = f"[{root.operator_type}] {root.detail}"
        if root.is_bottleneck:
            node_label += " [*** BOTTLENECK ***]"

        if root.operator_type == "ROOT" and not prefix:
            lines.append(f"ROOT: {root.detail}")
            new_prefix = ""
        else:
            lines.append(f"{prefix}{marker}{node_label}")
            new_prefix = prefix + ("    " if is_last else "|   ")

        for i, child in enumerate(root.children):
            is_child_last = (i == len(root.children) - 1)
            lines.append(cls.format_ascii_tree(child, new_prefix, is_child_last))

        return "\n".join(lines)
