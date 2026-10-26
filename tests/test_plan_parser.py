"""Unit Test Suite for Component 1: Physical Plan AST Parser.

Verifies flat explain plan ingestion, recursive PlanNode tree construction,
operator classification, bottleneck tagging, and ASCII tree rendering.
"""

import pytest
from src.engine.plan_parser import PlanASTParser, PlanNode


def test_parse_simple_scan_plan():
    """Verifies parsing of a simple sequential scan."""
    raw_rows = [
        (2, 0, 0, "SCAN lineitem"),
        (3, 0, 0, "USE TEMP B-TREE FOR GROUP BY")
    ]
    table_counts = {"lineitem": 60000}

    root = PlanASTParser.parse_sqlite_plan(raw_rows, table_row_counts=table_counts)
    assert root.operator_type == "ROOT"
    assert len(root.children) == 2

    scan_node = root.children[0]
    assert scan_node.operator_type == "SCAN"
    assert scan_node.table_name == "lineitem"
    assert scan_node.is_bottleneck is True

    sort_node = root.children[1]
    assert sort_node.operator_type == "SORT"
    assert sort_node.is_bottleneck is False


def test_parse_index_scan_plan():
    """Verifies parsing of standard and covering index scans."""
    raw_rows = [
        (3, 0, 0, "SEARCH lineitem USING INDEX idx_lineitem_shipdate (l_shipdate=?)"),
        (4, 0, 0, "SEARCH customer USING COVERING INDEX idx_cust_cov (c_custkey=?)")
    ]

    root = PlanASTParser.parse_sqlite_plan(raw_rows)
    assert len(root.children) == 2

    idx_scan = root.children[0]
    assert idx_scan.operator_type == "INDEX_SCAN"
    assert idx_scan.table_name == "lineitem"
    assert idx_scan.index_name == "idx_lineitem_shipdate"
    assert idx_scan.is_bottleneck is False

    cov_scan = root.children[1]
    assert cov_scan.operator_type == "COVERING_INDEX_SCAN"
    assert cov_scan.table_name == "customer"
    assert cov_scan.index_name == "idx_cust_cov"


def test_extract_bottlenecks():
    """Verifies isolation of bottleneck leaf operators."""
    raw_rows = [
        (2, 0, 0, "SCAN lineitem"),
        (3, 0, 0, "SCAN region"),
        (4, 0, 0, "SEARCH orders USING INDEX idx_orders_key")
    ]
    # lineitem is large, region is small (5 rows)
    table_counts = {"lineitem": 60000, "region": 5, "orders": 15000}

    root = PlanASTParser.parse_sqlite_plan(raw_rows, table_row_counts=table_counts, bottleneck_row_threshold=1000)
    bottlenecks = PlanASTParser.extract_bottlenecks(root)

    assert len(bottlenecks) == 1
    assert bottlenecks[0].table_name == "lineitem"
    assert bottlenecks[0].operator_type == "SCAN"


def test_format_ascii_tree():
    """Verifies human-readable ASCII tree rendering."""
    raw_rows = [
        (2, 0, 0, "SCAN lineitem"),
        (3, 0, 0, "USE TEMP B-TREE FOR ORDER BY")
    ]
    root = PlanASTParser.parse_sqlite_plan(raw_rows, table_row_counts={"lineitem": 5000})
    tree_str = PlanASTParser.format_ascii_tree(root)

    assert "ROOT:" in tree_str
    assert "[SCAN] SCAN lineitem" in tree_str
    assert "[*** BOTTLENECK ***]" in tree_str
    assert "[SORT] USE TEMP B-TREE FOR ORDER BY" in tree_str


def test_node_helper_methods():
    """Tests find_nodes_by_type and find_scans_by_table."""
    raw_rows = [
        (2, 0, 0, "SCAN lineitem"),
        (3, 0, 0, "SEARCH lineitem USING INDEX idx_l"),
        (4, 0, 0, "SCAN orders")
    ]
    root = PlanASTParser.parse_sqlite_plan(raw_rows)

    all_scans = root.find_nodes_by_type("SCAN")
    assert len(all_scans) == 2

    lineitem_scans = root.find_scans_by_table("lineitem")
    assert len(lineitem_scans) == 2  # 1 SCAN + 1 INDEX_SCAN
