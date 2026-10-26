"""TPC-H Analytical Query Workload Suite.

Defines iconic TPC-H query archetypes (Q1, Q3, Q6, Q10, Q12) with execution weights
and physical bottleneck descriptions.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass(frozen=True)
class WorkloadQuery:
    query_id: str
    name: str
    sql: str
    weight: float = 1.0
    description: str = ""


# 1. Query 1: Pricing Summary Report
# Bottleneck: Heavy range scan and aggregation over lineitem on l_shipdate
TPCH_Q1_SQL = """
SELECT 
    l_returnflag, 
    l_linestatus, 
    sum(l_quantity) AS sum_qty, 
    sum(l_extendedprice) AS sum_base_price, 
    sum(l_extendedprice * (1 - l_discount)) AS sum_disc_price, 
    sum(l_extendedprice * (1 - l_discount) * (1 + l_tax)) AS sum_charge, 
    avg(l_quantity) AS avg_qty, 
    avg(l_extendedprice) AS avg_price, 
    avg(l_discount) AS avg_disc, 
    count(*) AS count_order
FROM lineitem
WHERE l_shipdate <= '1998-09-02'
GROUP BY l_returnflag, l_linestatus
ORDER BY l_returnflag, l_linestatus;
"""

# 2. Query 3: Shipping Priority Query
# Bottleneck: 3-table join (customer, orders, lineitem) with top-K sort
TPCH_Q3_SQL = """
SELECT 
    l_orderkey, 
    sum(l_extendedprice * (1 - l_discount)) AS revenue, 
    o_orderdate, 
    o_shippriority
FROM customer, orders, lineitem
WHERE c_mktsegment = 'BUILDING'
  AND c_custkey = o_custkey
  AND l_orderkey = o_orderkey
  AND o_orderdate < '1995-03-15'
  AND l_shipdate > '1995-03-15'
GROUP BY l_orderkey, o_orderdate, o_shippriority
ORDER BY revenue DESC
LIMIT 10;
"""

# 3. Query 6: Forecasting Revenue Change Query
# Bottleneck: Multi-attribute conjunction on (l_shipdate, l_discount, l_quantity)
# Prime candidate for composite indexing
TPCH_Q6_SQL = """
SELECT sum(l_extendedprice * l_discount) AS revenue
FROM lineitem
WHERE l_shipdate >= '1994-01-01'
  AND l_shipdate < '1995-01-01'
  AND l_discount BETWEEN 0.05 AND 0.07
  AND l_quantity < 24;
"""

# 4. Query 10: Returned Item Reporting Query
# Bottleneck: 4-table join with filter on l_returnflag = 'R' and o_orderdate range
TPCH_Q10_SQL = """
SELECT 
    c_custkey, 
    c_name, 
    sum(l_extendedprice * (1 - l_discount)) AS revenue, 
    c_acctbal, 
    n_name, 
    c_address, 
    c_phone, 
    c_comment
FROM customer, orders, lineitem, nation
WHERE c_custkey = o_custkey
  AND l_orderkey = o_orderkey
  AND o_orderdate >= '1993-10-01'
  AND o_orderdate < '1994-01-01'
  AND l_returnflag = 'R'
  AND c_nationkey = n_nationkey
GROUP BY c_custkey, c_name, c_acctbal, c_phone, n_name, c_address, c_comment
ORDER BY revenue DESC
LIMIT 20;
"""

# 5. Query 12: Shipping Modes and Order Priority Query
# Bottleneck: Join on orders and lineitem filtering on l_shipmode IN (...) and date range
TPCH_Q12_SQL = """
SELECT 
    l_shipmode,
    sum(CASE WHEN o_orderpriority = '1-URGENT' OR o_orderpriority = '2-HIGH' THEN 1 ELSE 0 END) AS high_line_count,
    sum(CASE WHEN o_orderpriority <> '1-URGENT' AND o_orderpriority <> '2-HIGH' THEN 1 ELSE 0 END) AS low_line_count
FROM orders, lineitem
WHERE o_orderkey = l_orderkey
  AND l_shipmode IN ('MAIL', 'SHIP')
  AND l_commitdate < l_receiptdate
  AND l_shipdate < l_commitdate
  AND l_receiptdate >= '1994-01-01'
  AND l_receiptdate < '1995-01-01'
GROUP BY l_shipmode
ORDER BY l_shipmode;
"""

DEFAULT_WORKLOAD: List[WorkloadQuery] = [
    WorkloadQuery(
        query_id="Q1",
        name="Pricing Summary Report",
        sql=TPCH_Q1_SQL.strip(),
        weight=1.0,
        description="Scans large lineitem slice with date filter and aggregates return/status groups."
    ),
    WorkloadQuery(
        query_id="Q3",
        name="Shipping Priority",
        sql=TPCH_Q3_SQL.strip(),
        weight=1.5,
        description="Joins customer, orders, lineitem with market segment filter and top-K sort."
    ),
    WorkloadQuery(
        query_id="Q6",
        name="Forecasting Revenue Change",
        sql=TPCH_Q6_SQL.strip(),
        weight=1.2,
        description="Conjunctive filter over shipdate, discount, and quantity. Tests composite index synthesis."
    ),
    WorkloadQuery(
        query_id="Q10",
        name="Returned Item Reporting",
        sql=TPCH_Q10_SQL.strip(),
        weight=1.0,
        description="Four-table join tracking customers with returned items in a given quarter."
    ),
    WorkloadQuery(
        query_id="Q12",
        name="Shipping Modes and Order Priority",
        sql=TPCH_Q12_SQL.strip(),
        weight=1.0,
        description="Multi-date constraint join tracking priority fulfillment rates across ship modes."
    ),
]


def get_tpch_workload() -> List[WorkloadQuery]:
    """Returns the standardized TPC-H 5-query workload suite."""
    return list(DEFAULT_WORKLOAD)


def get_query_by_id(query_id: str) -> Optional[WorkloadQuery]:
    """Retrieves a single workload query by identifier (e.g. 'Q6')."""
    for q in DEFAULT_WORKLOAD:
        if q.query_id.upper() == query_id.upper():
            return q
    return None
