"""Database Connector Abstraction & SQLite Engine Implementation.

Provides an abstract interface DatabaseConnector and a concrete SQLiteConnector
supporting execution plan analysis (EXPLAIN QUERY PLAN) and physical page tracking.
"""

from abc import ABC, abstractmethod
import sqlite3
import time
from typing import List, Tuple, Dict, Any, Optional


class DatabaseConnector(ABC):
    """Abstract interface for database engines in AutoTune-DB."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to database."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> List[Tuple]:
        """Execute a single query and return all fetched rows."""
        pass

    @abstractmethod
    def executescript(self, sql_script: str) -> None:
        """Execute multiple SQL statements (e.g., DDL scripts)."""
        pass

    @abstractmethod
    def explain(self, sql: str, params: tuple = ()) -> List[Tuple]:
        """Return the physical execution plan for a SQL query."""
        pass

    @abstractmethod
    def create_index(self, table: str, columns: List[str], index_name: str) -> int:
        """Create physical index and return allocated size in bytes."""
        pass

    @abstractmethod
    def drop_index(self, index_name: str) -> None:
        """Drop a physical index."""
        pass

    @abstractmethod
    def get_index_size_bytes(self, index_name: str) -> int:
        """Return physical storage footprint of index in bytes."""
        pass

    @abstractmethod
    def get_table_cardinality(self, table: str, column: str) -> float:
        """Return selectivity / cardinality ratio: |Distinct(C)| / |TotalRows|."""
        pass

    @abstractmethod
    def get_table_row_count(self, table: str) -> int:
        """Return total row count of relation."""
        pass

    @abstractmethod
    def get_active_indexes(self, table: Optional[str] = None) -> List[Dict[str, Any]]:
        """List active non-primary secondary indexes."""
        pass


class SQLiteConnector(DatabaseConnector):
    """Concrete SQLite connector with execution plan and physical page tracking."""

    def __init__(self, db_path: str = ":memory:", page_size: int = 4096):
        self.db_path = db_path
        self.page_size = page_size
        self._conn: Optional[sqlite3.Connection] = None
        self._index_sizes: Dict[str, int] = {}
        self.connect()

    def connect(self) -> None:
        if self._conn is not None:
            return
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = None
        cur = self._conn.cursor()
        cur.execute(f"PRAGMA page_size = {self.page_size};")
        cur.execute("PRAGMA cache_size = -64000;")  # 64MB cache
        cur.execute("PRAGMA temp_store = MEMORY;")
        cur.execute("PRAGMA synchronous = NORMAL;")
        cur.execute("PRAGMA foreign_keys = ON;")
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str, params: tuple = ()) -> List[Tuple]:
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def executescript(self, sql_script: str) -> None:
        if self._conn is None:
            self.connect()
        self._conn.executescript(sql_script)
        self._conn.commit()

    def explain(self, sql: str, params: tuple = ()) -> List[Tuple]:
        """Returns SQLite EXPLAIN QUERY PLAN rows: (id, parent, notused, detail)."""
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        try:
            cur.execute(f"EXPLAIN QUERY PLAN {sql}", params)
            return cur.fetchall()
        finally:
            cur.close()

    def _get_page_count(self) -> int:
        cur = self._conn.cursor()
        try:
            res = cur.execute("PRAGMA page_count;").fetchone()
            return res[0] if res else 0
        finally:
            cur.close()

    def create_index(self, table: str, columns: List[str], index_name: str) -> int:
        """Creates physical B-Tree index and tracks its page allocation."""
        if self._conn is None:
            self.connect()
        cols_str = ", ".join(columns)
        pages_before = self._get_page_count()

        cur = self._conn.cursor()
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({cols_str});")
            self._conn.commit()
        finally:
            cur.close()

        pages_after = self._get_page_count()
        delta_pages = max(0, pages_after - pages_before)

        # If page_count grew, use exact physical page growth
        if delta_pages > 0:
            size_bytes = delta_pages * self.page_size
        else:
            # For in-memory or small allocations where pre-allocated pages were used:
            # Estimate B-Tree leaf allocation: (row_count * (avg_key_bytes + 8)) with 70% fill factor
            row_count = self.get_table_row_count(table)
            key_width_estimate = sum(8 for _ in columns)  # conservative 8 bytes per column key
            leaf_bytes = int((row_count * (key_width_estimate + 8)) / 0.70)
            size_bytes = max(self.page_size, leaf_bytes)

        self._index_sizes[index_name] = size_bytes
        return size_bytes

    def drop_index(self, index_name: str) -> None:
        """Drops index and removes tracked size."""
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        try:
            cur.execute(f"DROP INDEX IF EXISTS {index_name};")
            self._conn.commit()
        finally:
            cur.close()
        self._index_sizes.pop(index_name, None)

    def get_index_size_bytes(self, index_name: str) -> int:
        """Returns tracked physical byte allocation of index."""
        if index_name in self._index_sizes:
            return self._index_sizes[index_name]

        # Check if dbstat is available
        try:
            cur = self._conn.cursor()
            try:
                cur.execute("SELECT COALESCE(SUM(pgsize), 0) FROM dbstat WHERE name = ?;", (index_name,))
                row = cur.fetchone()
                if row and row[0] > 0:
                    self._index_sizes[index_name] = row[0]
                    return row[0]
            finally:
                cur.close()
        except sqlite3.OperationalError:
            pass

        # Default fallback
        return self.page_size

    def get_table_cardinality(self, table: str, column: str) -> float:
        """Calculates ratio of distinct values to total rows: |Distinct(C)| / |TotalRows|."""
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        try:
            cur.execute(f"SELECT COUNT(DISTINCT {column}), COUNT(*) FROM {table};")
            row = cur.fetchone()
            if not row or row[1] == 0:
                return 0.0
            return float(row[0]) / float(row[1])
        finally:
            cur.close()

    def get_table_row_count(self, table: str) -> int:
        """Returns total rows in table."""
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            row = cur.fetchone()
            return row[0] if row else 0
        finally:
            cur.close()

    def get_active_indexes(self, table: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns metadata for all non-system secondary indexes."""
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        try:
            if table:
                cur.execute(f"PRAGMA index_list({table});")
                rows = cur.fetchall()
                # PRAGMA index_list returns: (seq, name, unique, origin, partial)
                indexes = []
                for r in rows:
                    name = r[1]
                    if not name.startswith("sqlite_autoindex"):
                        # Get index columns
                        cur.execute(f"PRAGMA index_info({name});")
                        cols = [c[2] for c in cur.fetchall()]
                        indexes.append({
                            "name": name,
                            "table": table,
                            "columns": cols,
                            "unique": bool(r[2]),
                            "size_bytes": self.get_index_size_bytes(name)
                        })
                return indexes
            else:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                tables = [r[0] for r in cur.fetchall()]
                all_indexes = []
                for t in tables:
                    all_indexes.extend(self.get_active_indexes(t))
                return all_indexes
        finally:
            cur.close()
