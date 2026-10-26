# PHASE1_THEORY_AND_ARCHITECTURE.md
# Phase 1: Database Engine Layer, TPC-H Schema & Workload Harness

**Project:** AutoTune-DB - Hierarchical Hybrid Autonomous Agent for Physical Database Design  
**Course:** UMC301 - Applied Data Science and Artificial Intelligence  
**Institution:** Indian Institute of Science (IISc), Computational and Data Sciences (CDS)  
**Instructor:** Prof. Deepak Subramani  
**Methodology:** Spec-Driven Development (SDD) - Chapter 13  
**Spec References:** [SPEC.md](file:///c:/Users/aksha/DSAI_Projects/Project4_AutoTune_DB/SPEC.md) | [PLAN.md](file:///c:/Users/aksha/DSAI_Projects/Project4_AutoTune_DB/PLAN.md)  

---

## 1. Executive Summary & Role in the AutoTune-DB Lifecycle

Before any autonomous agent can optimize a database, it requires a **concrete, deterministic, physical environment** where queries execute, disk pages are allocated, and execution plans can be inspected.

Phase 1 constructs this foundation:
* It establishes an abstract, extensible database interface (`DatabaseConnector`) implemented via an offline, zero-network, local SQLite engine with physical page tracking.
* It implements the full **TPC-H 8-table relational snowflake schema** and a configurable synthetic data populator ($SF \in [0.01, 1.0]$).
* It standardizes a representative analytical query workload ($\text{Q1, Q3, Q6, Q10, Q12}$) representing distinct query bottleneck archetypes.
* It defines **Acceptance Gate 1**, ensuring that unindexed baseline execution times, sequential scan plans, and physical index byte measurements are verified through automated unit tests.

```
       [REGION]
          | (1:N)
       [NATION]
       /      \
 (1:N)/        \(1:N)
  [SUPPLIER]  [CUSTOMER]
      \        /
 (1:N) \      / (1:N)
      [PARTSUPP] - - [ORDERS]
          |              | (1:N)
       [PART]        [LINEITEM]  <--- The "Giant" Fact Table (80% of data)
```

---

## 2. Core Theoretical Foundations

### 2.1 OLTP vs. OLAP (Decision Support)
In database systems engineering, workloads diverge into two fundamental paradigms:
1. **OLTP (Online Transaction Processing):** High-concurrency, short-lived point operations that update or retrieve individual records via primary keys (e.g., `SELECT balance FROM accounts WHERE user_id = 101`). These require simple B-Tree primary key lookups taking sub-millisecond time.
2. **OLAP (Online Analytical Processing):** Complex, long-running queries scanning hundreds of thousands or millions of records across multi-table join graphs to compute aggregations, identify trends, and evaluate business metrics (e.g., revenue forecasting, inventory reporting).

**TPC-H** is the globally recognized gold standard for OLAP decision support. It models an international wholesale supplier operating across regions, nations, customers, suppliers, and parts.

### 2.2 Physical Storage: Pages, Slotted Pages, and Heap Files
Relational databases store tables on disk within fixed-size memory blocks called **Pages** (typically $4\,096$ bytes in SQLite and PostgreSQL).
* **Heap Organization:** Records are packed into pages without any guaranteed physical ordering.
* **The Sequential Scan Tax:** In an unindexed database, evaluating a predicate such as `WHERE l_shipdate <= '1998-12-01'` forces the database engine to perform a **Full Table Scan (`Seq Scan`)**:
  1. The storage manager reads **every single page** allocated to the table from disk into the buffer pool.
  2. The execution engine unpacks every slotted tuple in memory.
  3. The filter condition is evaluated for each row.
* On a table with $6\,000\,000$ rows occupying $150\,000$ pages, an unindexed query triggers $150\,000$ page reads. Running five such queries consecutively saturates I/O channels and CPU caches.

### 2.3 The Physical Index Trade-off: Query Acceleration vs. Storage Footprint
A secondary B-Tree index copies selected column keys and their corresponding row IDs (`rowid`) into a balanced multi-way tree structure:
* **The Benefit:** Queries matching the index key prefix avoid sequential scans, performing targeted logarithmic B-Tree traversals ($h = \lceil \log_B(N) \rceil$) followed by a contiguous range scan over leaf pages.
* **The Storage Cost:** Every index consumes physical disk pages. A composite index over `lineitem(l_shipdate, l_discount, l_quantity)` on a large table can consume $50\text{–}100\text{ MB}$.
* **The Maintenance Penalty:** Write operations (`INSERT`, `UPDATE`, `DELETE`) suffer latency degradation because every active B-Tree index on the relation must be kept physically synchronized.

**The Golden Objective:** Under a strict storage budget $B$ (e.g., $B \le 25\text{ MB}$), identify the exact subset of single and composite indexes that yields maximum cumulative latency reduction across the analytical workload without exceeding $B$.

### 2.4 Physical Page Allocation & Exact Byte Tracking via SQLite `dbstat`
In many toy academic projects, index storage is estimated using crude string-length heuristics ($N_{\text{rows}} \times \text{KeyBytes}$). In production systems engineering, this is invalid because it ignores B-Tree page fill factors, internal node pointers, and page fragmentation.

SQLite provides an internal administrative virtual table: **`dbstat`**.
Querying `dbstat` yields the **exact physical page-level allocation**:
```sql
SELECT SUM(pgsize) AS total_bytes, COUNT(*) AS page_count 
FROM dbstat 
WHERE name = 'idx_lineitem_shipdate';
```
AutoTune-DB uses `dbstat` to enforce the **Storage Budget Hard-Limit Invariant** directly against engine truth.

---

## 3. Phase 1 Architecture & Modular Components

```
Project4_AutoTune_DB/
├── src/engine/
│   ├── db_connector.py     # Component 1: Abstract Database Connector & SQLite Implementation
│   ├── tpch_schema.py      # Component 2: 8-Table Relational DDL & Synthetic Populator
│   └── tpch_workload.py    # Component 3: Analytical Workload Suite & Query Weights
└── tests/
    └── test_engine.py      # Component 4: Acceptance Gate 1 (Automated Test Suite)
```

### Component 1: `src/engine/db_connector.py`
Defines the database interaction contract. Decouples the optimizer, MCTS search engine, and plan parser from engine-specific SQL dialects.

#### Interface Specification (`DatabaseConnector`):
```python
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional

class DatabaseConnector(ABC):
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to database instance."""
        pass

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> List[Tuple]:
        """Execute query and return result rows."""
        pass

    @abstractmethod
    def explain(self, sql: str) -> List[Tuple]:
        """Return raw query execution plan."""
        pass

    @abstractmethod
    def create_index(self, table: str, columns: List[str], index_name: str) -> int:
        """Physically create index and return its physical size in bytes."""
        pass

    @abstractmethod
    def drop_index(self, index_name: str) -> None:
        """Drop physical index from database."""
        pass

    @abstractmethod
    def get_index_size_bytes(self, index_name: str) -> int:
        """Query physical page allocation in bytes for an existing index."""
        pass

    @abstractmethod
    def get_table_cardinality(self, table: str, column: str) -> float:
        """Return distinct value ratio: |Distinct(C)| / |TotalRows|."""
        pass

    @abstractmethod
    def get_table_row_count(self, table: str) -> int:
        """Return total row count of relation."""
        pass
```

#### `SQLiteConnector` Implementation Highlights:
* Operates locally in memory (`:memory:`) or against persistent file storage (`data/tpch_data/tpch_sf01.db`).
* Enables low-level opcode and execution plan extraction via `EXPLAIN QUERY PLAN <sql>`.
* Queries `dbstat` virtual table to measure physical page sizes accurately.
* Calculates exact column cardinality via `SELECT COUNT(DISTINCT col), COUNT(*) FROM table`.

---

### Component 2: `src/engine/tpch_schema.py`
Encapsulates relational DDL and synthetic data populator with configurable scale factors ($SF$).

#### The 8 Relational Tables:
1. **`region`:** 5 records (Africa, America, Asia, Europe, Middle East).
2. **`nation`:** 25 records mapped to corresponding region keys.
3. **`supplier`:** $10\,000 \times SF$ records. Supplier account balance, address, nation key.
4. **`customer`:** $150\,000 \times SF$ records. Market segments (`AUTOMOBILE`, `BUILDING`, `FURNITURE`, `MACHINERY`, `HOUSEHOLD`).
5. **`part`:** $200\,000 \times SF$ records. Manufacturer, brand, retail price.
6. **`partsupp`:** $800\,000 \times SF$ records. Composite primary key `(ps_partkey, ps_suppkey)`.
7. **`orders`:** $1\,500\,000 \times SF$ records. Customer link, order date, order priority, shipping priority.
8. **`lineitem`:** $\approx 6\,000\,000 \times SF$ records. The core fact table containing 16 columns (ship dates, receipt dates, discount, quantity, return flags).

#### Scale Factor ($SF$) Configurations:
* **$SF = 0.01$ (Fast Unit Test Mode):** Generates $\approx 60\,000$ line items in $<2$ seconds. Ideal for automated CI/CD and unit tests.
* **$SF = 0.1$ (Interactive Benchmark Mode):** Generates $\approx 600\,000$ line items. Queries take measurable milliseconds (50ms–2000ms), demonstrating clear index acceleration.
* **$SF = 1.0$ (Full Standard Benchmark):** Generates $6\,000\,000$ line items for production-grade evaluation.

---

### Component 3: `src/engine/tpch_workload.py`
Standardizes five high-value analytical query archetypes from the official TPC-H specification, each testing a distinct physical indexing bottleneck:

```python
@dataclass(frozen=True)
class WorkloadQuery:
    query_id: str
    name: str
    sql: str
    weight: float = 1.0
    description: str = ""
```

#### The 5 Selected Query Archetypes:

#### 1. Query 1 (Pricing Summary Report) - Heavy Date Range Aggregation
* **Business Goal:** Reports summary statistics on line items shipped before a critical date, grouped by return flag and status.
* **SQL Structure:**
  ```sql
  SELECT 
      l_returnflag, 
      l_linestatus, 
      sum(l_quantity) AS sum_qty, 
      sum(l_extendedprice) AS sum_base_price, 
      avg(l_discount) AS avg_disc, 
      count(*) AS count_order
  FROM lineitem
  WHERE l_shipdate <= '1998-09-02'
  GROUP BY l_returnflag, l_linestatus
  ORDER BY l_returnflag, l_linestatus;
  ```
* **Bottleneck:** Full sequential scan over `lineitem`. Tests range index on `l_shipdate`.

#### 2. Query 3 (Shipping Priority) - Multi-Table Join with Top-K Ordering
* **Business Goal:** Retrieves unshipped orders with the highest revenue for building sector customers before a given date.
* **SQL Structure:**
  ```sql
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
  ```
* **Bottleneck:** 3-table join (`customer` $\bowtie$ `orders` $\bowtie$ `lineitem`). Tests foreign-key indexing and top-$K$ sorting.

#### 3. Query 6 (Forecasting Revenue Change) - Multi-Attribute Conjunction
* **Business Goal:** Quantifies revenue increase if discounts within a narrow band were eliminated on orders within a given year and quantity range.
* **SQL Structure:**
  ```sql
  SELECT sum(l_extendedprice * l_discount) AS revenue
  FROM lineitem
  WHERE l_shipdate >= '1994-01-01' 
    AND l_shipdate < '1995-01-01'
    AND l_discount BETWEEN 0.05 AND 0.07
    AND l_quantity < 24;
  ```
* **Bottleneck:** Conjunction over 3 attributes on the same table. **Ideal test case for Composite Index Synthesis** on `(l_shipdate, l_discount, l_quantity)`.

#### 4. Query 10 (Returned Item Reporting) - Complex Multi-Table Join with Filter
* **Business Goal:** Identifies customers who received returned items to assess customer service issues.
* **SQL Structure:**
  ```sql
  SELECT 
      c_custkey, c_name, 
      sum(l_extendedprice * (1 - l_discount)) AS revenue, 
      c_acctbal, n_name, c_address, c_phone, c_comment
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
  ```
* **Bottleneck:** 4-table join with mixed equality (`l_returnflag = 'R'`) and date range filters.

#### 5. Query 12 (Shipping Modes and Order Priority) - Date Range Join Filter
* **Business Goal:** Analyzes whether low-priority shipping modes affect critical order delivery commitments.
* **SQL Structure:**
  ```sql
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
  ```
* **Bottleneck:** Evaluates complex date inequality comparisons across joined relations.

---

### Component 4: `tests/test_engine.py` (Acceptance Gate 1)

In alignment with Spec-Driven Development (SDD), Phase 1 is validated by an automated test suite verifying five concrete system invariants:

1. **Schema Integrity:** All 8 tables exist with primary keys and expected columns.
2. **Referential Consistency:** Populated rows satisfy foreign key linkages (`l_orderkey` maps to existing `o_orderkey`).
3. **Unindexed Workload Baseline:** All 5 queries execute successfully on the unindexed database, returning non-empty result sets and recording wall-clock execution latencies.
4. **Execution Plan Inspection:** `EXPLAIN QUERY PLAN` confirms presence of `SCAN TABLE lineitem` in unindexed state.
5. **Physical Index Lifecycle & Size Profiling:** Creating a composite index generates $>0$ bytes in `dbstat`, accelerates a target query, and cleanly drops without resource leaks.

---

## 4. End-to-End Phase 1 Data Flow

```mermaid
sequenceDiagram
    autonumber
    participant Test as test_engine.py
    participant Conn as SQLiteConnector
    participant Schema as tpch_schema.py
    participant Workload as tpch_workload.py

    Note over Test,Conn: 1. Connection Initialization
    Test->>Conn: Initialize SQLiteConnector (database_path)
    Conn->>Conn: PRAGMA foreign_keys = ON; PRAGMA page_size = 4096;

    Note over Test,Schema: 2. Schema DDL & Data Population
    Test->>Schema: create_tpch_schema(connector)
    Schema->>Conn: Execute DDL (8 tables created)
    Test->>Schema: populate_synthetic_tpch(connector, sf=0.01, seed=42)
    Schema->>Conn: Bulk INSERT region, nation, supplier, customer, part, partsupp, orders, lineitem

    Note over Test,Workload: 3. Unindexed Baseline Profiling
    Test->>Workload: get_tpch_workload()
    loop For each WorkloadQuery Q1..Q12
        Test->>Conn: explain(Q_i.sql)
        Conn-->>Test: Raw Opcode Plan (SCAN TABLE lineitem)
        Test->>Conn: execute(Q_i.sql)
        Conn-->>Test: Rows returned + baseline latency (ms)
    end

    Note over Test,Conn: 4. Physical Index Lifecycle Verification
    Test->>Conn: create_index("lineitem", ["l_shipdate", "l_discount"], "idx_test")
    Conn->>Conn: CREATE INDEX idx_test ON lineitem (l_shipdate, l_discount)
    Test->>Conn: get_index_size_bytes("idx_test")
    Conn-->>Test: Returns exact bytes allocated via dbstat (e.g. 245,760 bytes)
    Test->>Conn: drop_index("idx_test")
    Conn-->>Test: Index dropped cleanly
```

---

## 5. How Phase 1 Enables Downstream Phases

* **Phase 2 (Plan AST Parser & Hypo-Cost Engine):** Uses the `explain()` outputs generated in Phase 1 to construct typed `PlanNode` trees and benchmark the zero-byte hypothetical cost simulator against real execution times.
* **Phase 3 (Stage 1: AST Semantic Miner):** Parses the SQL text defined in `tpch_workload.py` to extract candidate single and composite index keys.
* **Phase 4 (Stage 2: MCTS Combinatorial Solver):** Uses candidate index sizes measured via `get_index_size_bytes()` to enforce storage budget constraints $B$.
* **Phase 5 (Stage 3: Live DB Verification & 4-Way Ablation):** Runs the full 4-way ablation benchmark against this exact database instance, reporting wall-clock speedup metrics.
