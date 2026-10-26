"""Standard TPC-H 8-Table Schema DDL & Synthetic Data Populator.

Defines the relational snowflake schema for TPC-H and implements a deterministic
synthetic data generator supporting scale factors SF=0.001 to SF=1.0.
"""

import datetime
import random
from typing import List, Tuple, Dict
from src.engine.db_connector import DatabaseConnector

TPCH_DDL = """
-- 1. REGION Table
CREATE TABLE IF NOT EXISTS region (
    r_regionkey INTEGER PRIMARY KEY,
    r_name VARCHAR(25) NOT NULL,
    r_comment VARCHAR(152)
);

-- 2. NATION Table
CREATE TABLE IF NOT EXISTS nation (
    n_nationkey INTEGER PRIMARY KEY,
    n_name VARCHAR(25) NOT NULL,
    n_regionkey INTEGER NOT NULL REFERENCES region(r_regionkey),
    n_comment VARCHAR(152)
);

-- 3. SUPPLIER Table
CREATE TABLE IF NOT EXISTS supplier (
    s_suppkey INTEGER PRIMARY KEY,
    s_name VARCHAR(25) NOT NULL,
    s_address VARCHAR(40) NOT NULL,
    s_nationkey INTEGER NOT NULL REFERENCES nation(n_nationkey),
    s_phone VARCHAR(15) NOT NULL,
    s_acctbal DECIMAL(15, 2) NOT NULL,
    s_comment VARCHAR(101)
);

-- 4. CUSTOMER Table
CREATE TABLE IF NOT EXISTS customer (
    c_custkey INTEGER PRIMARY KEY,
    c_name VARCHAR(25) NOT NULL,
    c_address VARCHAR(40) NOT NULL,
    c_nationkey INTEGER NOT NULL REFERENCES nation(n_nationkey),
    c_phone VARCHAR(15) NOT NULL,
    c_acctbal DECIMAL(15, 2) NOT NULL,
    c_mktsegment VARCHAR(10) NOT NULL,
    c_comment VARCHAR(117)
);

-- 5. PART Table
CREATE TABLE IF NOT EXISTS part (
    p_partkey INTEGER PRIMARY KEY,
    p_name VARCHAR(55) NOT NULL,
    p_mfgr VARCHAR(25) NOT NULL,
    p_brand VARCHAR(10) NOT NULL,
    p_type VARCHAR(25) NOT NULL,
    p_size INTEGER NOT NULL,
    p_container VARCHAR(10) NOT NULL,
    p_retailprice DECIMAL(15, 2) NOT NULL,
    p_comment VARCHAR(23)
);

-- 6. PARTSUPP Table
CREATE TABLE IF NOT EXISTS partsupp (
    ps_partkey INTEGER NOT NULL REFERENCES part(p_partkey),
    ps_suppkey INTEGER NOT NULL REFERENCES supplier(s_suppkey),
    ps_availqty INTEGER NOT NULL,
    ps_supplycost DECIMAL(15, 2) NOT NULL,
    ps_comment VARCHAR(199),
    PRIMARY KEY (ps_partkey, ps_suppkey)
);

-- 7. ORDERS Table
CREATE TABLE IF NOT EXISTS orders (
    o_orderkey INTEGER PRIMARY KEY,
    o_custkey INTEGER NOT NULL REFERENCES customer(c_custkey),
    o_orderstatus CHAR(1) NOT NULL,
    o_totalprice DECIMAL(15, 2) NOT NULL,
    o_orderdate DATE NOT NULL,
    o_orderpriority VARCHAR(15) NOT NULL,
    o_clerk VARCHAR(15) NOT NULL,
    o_shippriority INTEGER NOT NULL,
    o_comment VARCHAR(79)
);

-- 8. LINEITEM Table (The Fact Table)
CREATE TABLE IF NOT EXISTS lineitem (
    l_orderkey INTEGER NOT NULL REFERENCES orders(o_orderkey),
    l_partkey INTEGER NOT NULL REFERENCES part(p_partkey),
    l_suppkey INTEGER NOT NULL REFERENCES supplier(s_suppkey),
    l_linenumber INTEGER NOT NULL,
    l_quantity DECIMAL(15, 2) NOT NULL,
    l_extendedprice DECIMAL(15, 2) NOT NULL,
    l_discount DECIMAL(15, 2) NOT NULL,
    l_tax DECIMAL(15, 2) NOT NULL,
    l_returnflag CHAR(1) NOT NULL,
    l_linestatus CHAR(1) NOT NULL,
    l_shipdate DATE NOT NULL,
    l_commitdate DATE NOT NULL,
    l_receiptdate DATE NOT NULL,
    l_shipinstruct VARCHAR(25) NOT NULL,
    l_shipmode VARCHAR(10) NOT NULL,
    l_comment VARCHAR(44),
    PRIMARY KEY (l_orderkey, l_linenumber)
);
"""

REGIONS = [
    (0, "AFRICA", "Standard African distribution center"),
    (1, "AMERICA", "North and South America regional logistics"),
    (2, "ASIA", "Asia-Pacific supply hubs"),
    (3, "EUROPE", "Western and Eastern European distribution"),
    (4, "MIDDLE EAST", "Middle Eastern transit zones"),
]

NATIONS = [
    (0, "ALGERIA", 0), (1, "ARGENTINA", 1), (2, "BRAZIL", 1), (3, "CANADA", 1),
    (4, "EGYPT", 4), (5, "ETHIOPIA", 0), (6, "FRANCE", 3), (7, "GERMANY", 3),
    (8, "INDIA", 2), (9, "INDONESIA", 2), (10, "IRAN", 4), (11, "IRAQ", 4),
    (12, "JAPAN", 2), (13, "JORDAN", 4), (14, "KENYA", 0), (15, "MOROCCO", 0),
    (16, "MOZAMBIQUE", 0), (17, "PERU", 1), (18, "CHINA", 2), (19, "ROMANIA", 3),
    (20, "SAUDI ARABIA", 4), (21, "VIETNAM", 2), (22, "RUSSIA", 3), (23, "UNITED KINGDOM", 3),
    (24, "UNITED STATES", 1)
]

MARKET_SEGMENTS = ["AUTOMOBILE", "BUILDING", "FURNITURE", "MACHINERY", "HOUSEHOLD"]
ORDER_PRIORITIES = ["1-URGENT", "2-HIGH", "3-MEDIUM", "4-NOT SPECIFIED", "5-LOW"]
ORDER_STATUSES = ["O", "F", "P"]  # Open, Filled, Pending
RETURN_FLAGS = ["R", "A", "N"]    # Returned, Accepted, Neither
LINE_STATUSES = ["O", "F"]        # Open, Finished
SHIP_INSTRUCTS = ["DELIVER IN PERSON", "COLLECT COD", "NONE", "TAKE BACK RETURN"]
SHIP_MODES = ["AIR", "SHIP", "TRUCK", "MAIL", "RAIL", "REG AIR", "FOB"]


def create_tpch_schema(connector: DatabaseConnector) -> None:
    """Executes the DDL creating all 8 TPC-H relational tables."""
    connector.executescript(TPCH_DDL)


def drop_tpch_schema(connector: DatabaseConnector) -> None:
    """Drops all 8 TPC-H tables in reverse foreign key order."""
    drop_script = """
    DROP TABLE IF EXISTS lineitem;
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS partsupp;
    DROP TABLE IF EXISTS part;
    DROP TABLE IF EXISTS customer;
    DROP TABLE IF EXISTS supplier;
    DROP TABLE IF EXISTS nation;
    DROP TABLE IF EXISTS region;
    """
    connector.executescript(drop_script)


def populate_synthetic_tpch(
    connector: DatabaseConnector,
    scale_factor: float = 0.01,
    seed: int = 42
) -> Dict[str, int]:
    """Populates the database with synthetic TPC-H data scaled by scale_factor.
    
    Scale Factor = 0.01 yields:
      - 5 regions, 25 nations
      - 100 suppliers
      - 1,500 customers
      - 2,000 parts
      - 8,000 partsupp rows
      - 15,000 orders
      - ~60,000 line items
    """
    rng = random.Random(seed)
    
    # Scale counts with minimum floors
    num_suppliers = max(10, int(10000 * scale_factor))
    num_customers = max(50, int(150000 * scale_factor))
    num_parts = max(50, int(200000 * scale_factor))
    num_orders = max(100, int(1500000 * scale_factor))

    # Base dates
    start_date = datetime.date(1992, 1, 1)
    end_date = datetime.date(1998, 12, 31)
    total_days = (end_date - start_date).days

    # 1. Populate REGION
    region_rows = [(r[0], r[1], r[2]) for r in REGIONS]
    _bulk_insert(connector, "region", region_rows, 3)

    # 2. Populate NATION
    nation_rows = [(n[0], n[1], n[2], f"Nation comment {n[1]}") for n in NATIONS]
    _bulk_insert(connector, "nation", nation_rows, 4)

    # 3. Populate SUPPLIER
    supplier_rows = []
    for s_id in range(1, num_suppliers + 1):
        n_key = rng.randint(0, 24)
        acctbal = round(rng.uniform(-999.99, 9999.99), 2)
        supplier_rows.append((
            s_id, f"Supplier#{s_id:09d}", f"Address {s_id}",
            n_key, f"10-{rng.randint(100, 999)}-{rng.randint(100, 999)}",
            acctbal, f"Comment for supplier {s_id}"
        ))
    _bulk_insert(connector, "supplier", supplier_rows, 7)

    # 4. Populate CUSTOMER
    customer_rows = []
    for c_id in range(1, num_customers + 1):
        n_key = rng.randint(0, 24)
        acctbal = round(rng.uniform(-999.99, 9999.99), 2)
        mkt = rng.choice(MARKET_SEGMENTS)
        customer_rows.append((
            c_id, f"Customer#{c_id:09d}", f"Address {c_id}",
            n_key, f"20-{rng.randint(100, 999)}-{rng.randint(100, 999)}",
            acctbal, mkt, f"Comment for customer {c_id}"
        ))
    _bulk_insert(connector, "customer", customer_rows, 8)

    # 5. Populate PART
    part_rows = []
    for p_id in range(1, num_parts + 1):
        price = round(rng.uniform(10.0, 2000.0), 2)
        size = rng.randint(1, 50)
        part_rows.append((
            p_id, f"Part {p_id}", f"Manufacturer#{rng.randint(1, 5)}",
            f"Brand#{rng.randint(1, 5)}", "PROMO BRUSHED BRASS",
            size, "JUMBO BAG", price, f"Part comment {p_id}"
        ))
    _bulk_insert(connector, "part", part_rows, 9)

    # 6. Populate PARTSUPP (4 suppliers per part)
    partsupp_rows = []
    for p_id in range(1, num_parts + 1):
        chosen_suppliers = rng.sample(range(1, num_suppliers + 1), min(4, num_suppliers))
        for s_id in chosen_suppliers:
            availqty = rng.randint(1, 9999)
            supplycost = round(rng.uniform(1.0, 1000.0), 2)
            partsupp_rows.append((p_id, s_id, availqty, supplycost, f"Partsupp comment {p_id}-{s_id}"))
    _bulk_insert(connector, "partsupp", partsupp_rows, 5)

    # 7. Populate ORDERS & LINEITEM
    order_rows = []
    lineitem_rows = []

    for o_id in range(1, num_orders + 1):
        c_id = rng.randint(1, num_customers)
        status = rng.choice(ORDER_STATUSES)
        order_day_offset = rng.randint(0, total_days - 150)
        order_date = start_date + datetime.timedelta(days=order_day_offset)
        order_priority = rng.choice(ORDER_PRIORITIES)
        shippriority = rng.randint(0, 1)

        # 1 to 5 line items per order
        num_items = rng.randint(1, 5)
        order_total = 0.0

        for line_num in range(1, num_items + 1):
            p_id = rng.randint(1, num_parts)
            s_id = rng.randint(1, num_suppliers)
            quantity = float(rng.randint(1, 50))
            price_per_unit = round(rng.uniform(10.0, 1000.0), 2)
            extended_price = round(quantity * price_per_unit, 2)
            discount = round(rng.uniform(0.00, 0.10), 2)
            tax = round(rng.uniform(0.00, 0.08), 2)
            returnflag = rng.choice(RETURN_FLAGS)
            linestatus = rng.choice(LINE_STATUSES)

            # Dates: shipdate = orderdate + 1..120 days
            ship_date = order_date + datetime.timedelta(days=rng.randint(1, 120))
            commit_date = order_date + datetime.timedelta(days=rng.randint(30, 90))
            receipt_date = ship_date + datetime.timedelta(days=rng.randint(1, 30))

            shipinstruct = rng.choice(SHIP_INSTRUCTS)
            shipmode = rng.choice(SHIP_MODES)

            order_total += extended_price * (1.0 - discount) * (1.0 + tax)

            lineitem_rows.append((
                o_id, p_id, s_id, line_num,
                quantity, extended_price, discount, tax,
                returnflag, linestatus,
                ship_date.isoformat(), commit_date.isoformat(), receipt_date.isoformat(),
                shipinstruct, shipmode, f"Lineitem comment {o_id}_{line_num}"
            ))

        order_rows.append((
            o_id, c_id, status, round(order_total, 2),
            order_date.isoformat(), order_priority,
            f"Clerk#{rng.randint(1, 50):05d}", shippriority,
            f"Order comment {o_id}"
        ))

    _bulk_insert(connector, "orders", order_rows, 9)
    _bulk_insert(connector, "lineitem", lineitem_rows, 16)

    return {
        "region": len(region_rows),
        "nation": len(nation_rows),
        "supplier": len(supplier_rows),
        "customer": len(customer_rows),
        "part": len(part_rows),
        "partsupp": len(partsupp_rows),
        "orders": len(order_rows),
        "lineitem": len(lineitem_rows)
    }


def _bulk_insert(connector: DatabaseConnector, table: str, rows: List[Tuple], num_cols: int, batch_size: int = 5000) -> None:
    """Helper to insert rows in bulk batches for speed."""
    if not rows:
        return
    placeholders = ", ".join(["?"] * num_cols)
    sql = f"INSERT INTO {table} VALUES ({placeholders})"
    
    # If connector is SQLiteConnector, use executemany directly on connection
    if hasattr(connector, "_conn") and connector._conn is not None:
        cur = connector._conn.cursor()
        try:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                cur.executemany(sql, batch)
            connector._conn.commit()
        finally:
            cur.close()
    else:
        for r in rows:
            connector.execute(sql, r)
