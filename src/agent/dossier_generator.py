"""Stage 3: DBA Physical Design Dossier Generator.

Synthesizes an executive-grade physical database tuning report including
executable DDL statements, storage budgets, latency speedups, and query plan deltas.
"""

from typing import List, Dict, Optional
from src.agent.react_controller import VerificationResult, QueryBenchmarkResult
from src.engine.hypo_cost_engine import HypoIndex


class DossierGenerator:
    """Generates professional DBA Physical Design Dossiers."""

    @staticmethod
    def generate_markdown_dossier(
        result: VerificationResult,
        db_type: str = "SQLite 3 (B-Tree Engine)",
        scale_factor: float = 0.005,
        workload_name: str = "TPC-H Standard Analytics (Q1, Q3, Q6, Q10, Q12)"
    ) -> str:
        """Constructs a comprehensive, publication-ready physical database audit report."""
        lines = []

        # 1. Header & Title
        lines.append("# AutoTune-DB: DBA Physical Database Design Dossier")
        lines.append(f"**Target System:** {db_type}  ")
        lines.append(f"**Workload Suite:** {workload_name} (Scale Factor: {scale_factor})  ")
        lines.append(f"**Optimization Strategy:** Hierarchical Hybrid (AST Semantic Miner + MCTS Solver + Live Verifier)  ")
        lines.append("---")
        lines.append("")

        # 2. Executive Summary
        lines.append("## 1. Executive Summary")
        lines.append("")
        status_badge = "COMPLIANT" if result.budget_compliant else "NON-COMPLIANT"
        lines.append(f"- **Overall Wall-Clock Speedup:** **{result.workload_speedup:.2f}x**")
        lines.append(f"- **Total Workload Latency:** `{result.total_base_time_ms:.2f} ms` -> **`{result.total_opt_time_ms:.2f} ms`**")
        lines.append(f"- **Physical Storage Allocated:** `{result.storage_used_bytes / 1024:.1f} KB` / `{result.storage_budget_bytes / 1024:.1f} KB` ({status_badge})")
        lines.append(f"- **Indexes Recommended:** {len(result.active_indexes)}")
        lines.append(f"- **ReAct Reflection Cycles:** {result.reflection_cycles}")
        lines.append(f"- **CBO Plan Regressions Detected:** {len(result.regressions_detected)}")
        lines.append("")

        # 3. Recommended Physical DDL
        lines.append("## 2. Recommended Physical DDL Statements")
        lines.append("The following SQL statements constitute the Pareto-optimal physical index configuration:")
        lines.append("")
        lines.append("```sql")
        if not result.active_indexes:
            lines.append("-- No additional indexes recommended (existing layout or budget saturated)")
        else:
            for idx in result.active_indexes:
                cols_str = ", ".join(idx.columns)
                lines.append(f"CREATE INDEX IF NOT EXISTS {idx.name} ON {idx.table} ({cols_str});")
        lines.append("```")
        lines.append("")

        # 4. Storage Breakdown Table
        lines.append("## 3. Physical Storage Allocation Breakdown")
        lines.append("")
        lines.append("| Index Name | Target Table | Indexed Columns | Physical Size (KB) |")
        lines.append("| :--- | :--- | :--- | :--- |")
        if not result.active_indexes:
            lines.append("| *None* | - | - | 0.0 KB |")
        else:
            for idx in result.active_indexes:
                cols_str = "(`" + "`, `".join(idx.columns) + "`)"
                lines.append(f"| `{idx.name}` | `{idx.table}` | {cols_str} | `{(result.storage_used_bytes / max(1, len(result.active_indexes))) / 1024:.1f} KB` |")
        lines.append("")

        # 5. Query-Level Wall-Clock Performance Delta
        lines.append("## 4. Query-Level Performance Benchmark Delta")
        lines.append("")
        lines.append("| Query ID | Base Runtime (ms) | Opt Runtime (ms) | Speedup | Regressed? | Indexes Leveraged |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for q_id, q_res in result.query_results.items():
            reg_flag = "⚠️ REGRESSED" if q_res.has_regressed else "✅ PASS"
            used_str = ", ".join(f"`{u}`" for u in q_res.used_indexes) if q_res.used_indexes else "*Table Scan*"
            lines.append(
                f"| **{q_id}** | `{q_res.base_time_ms:.2f} ms` | `{q_res.opt_time_ms:.2f} ms` | "
                f"**{q_res.speedup_ratio:.2f}x** | {reg_flag} | {used_str} |"
            )
        lines.append("")

        # 6. Query Plan Transformations
        lines.append("## 5. Cost-Based Optimizer (CBO) Plan Transformations")
        lines.append("")
        for q_id, q_res in result.query_results.items():
            lines.append(f"### Query {q_id} Execution Plan Evolution")
            lines.append("")
            lines.append("**Baseline Plan (Unindexed):**")
            lines.append("```text")
            for row in q_res.base_plan_raw:
                detail = row[3] if len(row) > 3 else str(row)
                lines.append(f"- {detail}")
            lines.append("```")
            lines.append("")
            lines.append("**Optimized Plan (AutoTune-DB Layout):**")
            lines.append("```text")
            for row in q_res.opt_plan_raw:
                detail = row[3] if len(row) > 3 else str(row)
                lines.append(f"- {detail}")
            lines.append("```")
            lines.append("")

        # 7. Verification Audit Sign-off
        lines.append("## 6. Audit Verdict")
        if result.budget_compliant and result.workload_speedup > 1.0 and not result.regressions_detected:
            lines.append("> **APPROVED FOR PRODUCTION DEPLOYMENT**  ")
            lines.append("> Configuration provides strictly positive speedup, zero plan regressions, and 100% budget compliance.")
        else:
            lines.append("> **CONDITIONAL APPROVAL**  ")
            lines.append(f"> Workload speedup: {result.workload_speedup:.2f}x, Regressions: {len(result.regressions_detected)}.")

        return "\n".join(lines)
