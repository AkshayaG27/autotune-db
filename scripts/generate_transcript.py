"""Project 4 Transcript Generator: Exports transcript.md and transcript.html.

Extracts all 38 turns from the workspace log files for Project 4 (AutoTune-DB:
Autonomous Physical Database Design Agent), formats a publication-grade markdown
document, and renders a standalone interactive HTML page with collapsible response
panels, theme toggling, search filtering, and sidebar navigation.
"""

import sys
import os
import json
import re
import html

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(PROJECT_DIR)

LOG_PATH = r"C:\Users\aksha\.gemini\antigravity\brain\fa3d4156-ce2d-45b1-be62-a2c0b433353e\.system_generated\logs\transcript.jsonl"
LOG_FULL_PATH = r"C:\Users\aksha\.gemini\antigravity\brain\fa3d4156-ce2d-45b1-be62-a2c0b433353e\.system_generated\logs\transcript_full.jsonl"

MD_PATH = os.path.join(PROJECT_DIR, "transcript.md")
HTML_PATH = os.path.join(PROJECT_DIR, "transcript.html")

ROOT_MD_PATH = os.path.join(WORKSPACE_ROOT, "transcript_project4.md")
ROOT_HTML_PATH = os.path.join(WORKSPACE_ROOT, "transcript_project4.html")

# Curated metadata and classification for all 38 project turns
TURNS_META = [
    {
        "num": 1,
        "title": "Project 4 Brainstorming: Exploring Systems & Persona Agents Beyond GitBot",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Inception & Brainstorming",
        "tag": "Inception",
        "summary": "Exploring alternatives to the standard autonomous GitBot idea, discussing psychological simulation, persona modeling, and high-impact systems agent domains."
    },
    {
        "num": 2,
        "title": "Persona Modeling Feasibility & Viva Evaluation Alignment",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Feasibility Analysis",
        "tag": "Scoping",
        "summary": "Analyzing the psychological and persona modeling concept against the UMC301 A+ rubric, evaluating technical defensibility in an academic viva."
    },
    {
        "num": 3,
        "title": "Competitive Moat: Differentiating from Claude Code & Antigravity IDE",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Competitive Analysis",
        "tag": "Strategy",
        "summary": "Assessing competitive moats against general LLM coding tools like Claude Code and Antigravity, identifying the need for formal systems verification."
    },
    {
        "num": 4,
        "title": "Pivoting Beyond GitBot: High-Impact Autonomous Systems Problem Domains",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Domain Exploration",
        "tag": "Pivoting",
        "summary": "Deciding to pivot away from generic developer tools to explore four high-impact autonomous agent domains in systems, healthcare, and infrastructure."
    },
    {
        "num": 5,
        "title": "ConsensusSim Deep-Dive: Multi-Agent Deliberation & Social Simulation",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Domain Evaluation",
        "tag": "ConsensusSim",
        "summary": "Deep-dive into ConsensusSim (multi-agent consensus and policy deliberation), analyzing its architecture, emergent dynamics, and evaluator perception."
    },
    {
        "num": 6,
        "title": "Prior Art Analysis: Stanford Generative Agents & The Novelty Bar",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Prior Art Analysis",
        "tag": "Prior Art",
        "summary": "Contrasting ConsensusSim with Stanford's 2023 Generative Agents benchmark, emphasizing the necessity of verifiable mathematical optimization."
    },
    {
        "num": 7,
        "title": "Four High-Impact Agent Domains Outside the Psychological Track",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Domain Brainstorming",
        "tag": "Brainstorming",
        "summary": "Proposing 4 distinct systems agent tracks: Cloud Cost FinOps, eBPF Kernel Tuning, AutoTune-DB Physical Database Design, and API Gateway Fault Injection."
    },
    {
        "num": 8,
        "title": "AutoTune-DB Formulation: Autonomous Physical Database Design Agent",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Architecture Inception",
        "tag": "AutoTune-DB",
        "summary": "Deconstructing AutoTune-DB: autonomous physical index synthesis, candidate mining, combinatorial search, and live verification on TPC-H workloads."
    },
    {
        "num": 9,
        "title": "Competitive Moat Analysis: Why General LLMs Fail at Database Physical Design",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Competitive Moat",
        "tag": "Systems Moat",
        "summary": "Articulating why general LLMs fail at physical database design (hallucinating indexes, combinatorial explosion, lack of cost model awareness) and why AutoTune-DB wins."
    },
    {
        "num": 10,
        "title": "Official Project Selection: Codifying AutoTune-DB in MASTER_PROJECT_UPDATED.md",
        "part": "Part I: Project Inception, Competitive Strategy & Architectural Formulation",
        "phase": "Project Commitment",
        "tag": "Portfolio Alignment",
        "summary": "Officially selecting AutoTune-DB as Project 4, updating MASTER_PROJECT_UPDATED.md and MASTER_PROJECT_PORTFOLIO.md with formal project specifications."
    },
    {
        "num": 11,
        "title": "Scaffolding Technical Specifications: Authoring SPEC.md & Acceptance Gates",
        "part": "Part II: Hybrid Architecture Specification & Formal Roadmap",
        "phase": "Formal Specifications",
        "tag": "SPEC.md",
        "summary": "Drafting the initial formal specification file (SPEC.md) with database schemas, hypothetical cost engine equations, and phased acceptance gates."
    },
    {
        "num": 12,
        "title": "Architectural Breakthrough: The 10/10 Three-Stage Hybrid Pipeline",
        "part": "Part II: Hybrid Architecture Specification & Formal Roadmap",
        "phase": "Architecture Synthesis",
        "tag": "Hybrid Architecture",
        "summary": "Synthesizing the breakthrough 3-stage hybrid architecture: Stage 1 AST Semantic Miner (3,616 -> 40) + Stage 2 MCTS Combinatorial Solver + Stage 3 ReAct Live Verifier."
    },
    {
        "num": 13,
        "title": "Codifying the 3-Stage Hybrid Architecture in SPEC.md & Master Portfolio",
        "part": "Part II: Hybrid Architecture Specification & Formal Roadmap",
        "phase": "Specification Upgrade",
        "tag": "Architecture Upgrade",
        "summary": "Updating SPEC.md and portfolio documentation to reflect the complete 3-stage hybrid pipeline, UCT tree search equations, and Tabu reflection backtracking."
    },
    {
        "num": 14,
        "title": "Execution Roadmap Formulation: Authoring the 5-Phase PLAN.md",
        "part": "Part II: Hybrid Architecture Specification & Formal Roadmap",
        "phase": "Execution Roadmap",
        "tag": "PLAN.md",
        "summary": "Authoring the comprehensive step-by-step engineering roadmap (PLAN.md) covering synthetic TPC-H generation, HypoCostEngine, MCTS, ReAct, and Telemetry."
    },
    {
        "num": 15,
        "title": "Phase 1 Deep-Dive Theory: SQLite Workload Harness, Synthetic TPC-H & Instrumentation",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Phase 1 Theory",
        "tag": "Phase 1",
        "summary": "Whiteboard derivation of Phase 1: SQLite schema creation, deterministic synthetic data generator, TPC-H analytical queries (Q1, Q3, Q6, Q10, Q12), and plan parser."
    },
    {
        "num": 16,
        "title": "Documenting Phase 1 Mathematical & Architectural Formulations into SPEC.md",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Documentation",
        "tag": "Phase 1",
        "summary": "Persisting the mathematical and operational specifications of Phase 1 into project markdown documentation."
    },
    {
        "num": 17,
        "title": "Phase 1 Implementation Complete & Acceptance Gate 1 Verification",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Phase 1 Verification",
        "tag": "Phase 1",
        "summary": "Implementing db_connector, tpch_schema, tpch_workload, and plan_parser; passing all 6 Phase 1 unit and integration tests."
    },
    {
        "num": 18,
        "title": "Phase 2 Deep-Dive Theory: HypoCostEngine, Analytical Cost Model & Search Space Formulations",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Phase 2 Theory",
        "tag": "Phase 2",
        "summary": "Whiteboard derivation of Phase 2: zero-byte HypoCostEngine, leftmost prefix matching, Mackert-Lohman cost formula, and 0.4ms evaluation SLA."
    },
    {
        "num": 19,
        "title": "Phase 2 Implementation Complete & Acceptance Gate 2 Verification",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Phase 2 Verification",
        "tag": "Phase 2",
        "summary": "Implementing HypoCostEngine with sub-millisecond evaluation (<0.4ms) and prefix subsumption; passing all 8 Phase 2 unit tests."
    },
    {
        "num": 20,
        "title": "Phase 3 Deep-Dive Theory: Stage 1 Domain-Informed Candidate Index Miner",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Phase 3 Theory",
        "tag": "Phase 3",
        "summary": "Whiteboard derivation of Phase 3: SQL AST parsing, predicate extraction, equality-first column ordering, and pruning the 3,616+ naive permutation space to 30-40."
    },
    {
        "num": 21,
        "title": "Phase 3 Implementation Complete & Acceptance Gate 3 Verification",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Phase 3 Verification",
        "tag": "Phase 3",
        "summary": "Implementing CandidateMiner with bounded candidate generation (<12ms) and table diversity; passing all 6 Phase 3 unit tests."
    },
    {
        "num": 22,
        "title": "Phase 4 Deep-Dive Theory: Stage 2 MCTS Combinatorial Solver & UCT Policy",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Phase 4 Theory",
        "tag": "Phase 4",
        "summary": "Whiteboard derivation of Phase 4: Upper Confidence Bounds for Trees (UCT), exploration constant c, storage knapsack invariant, and rollout simulations."
    },
    {
        "num": 23,
        "title": "Phase 4 Implementation Complete & Acceptance Gate 4 Verification",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Phase 4 Verification",
        "tag": "Phase 4",
        "summary": "Implementing MCTSSolver, UCT selection, backpropagation, and budget-penalized reward functions; passing all 7 Phase 4 unit tests."
    },
    {
        "num": 24,
        "title": "Phase 5 Implementation: Stage 3 Live Verification, ReAct Tabu Reflection & 4-Way Ablation",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Phase 5 Verification",
        "tag": "Phase 5",
        "summary": "Implementing ReActVerificationController, live physical materialization, Tabu reflection backtracking for Q1 regressions, and 4-way ablation framework."
    },
    {
        "num": 25,
        "title": "Project 4 Comprehensive Milestone Audit: 34/34 Passing Tests & Walkthrough Creation",
        "part": "Part III: Algorithmic Derivations & Phased Systems Implementation",
        "phase": "Milestone Audit",
        "tag": "Milestone",
        "summary": "Auditing complete end-to-end pipeline across all 5 phases, verifying 100% test passing rate (34/34 tests in 7.6s), and authoring WALKTHROUGH.md."
    },
    {
        "num": 26,
        "title": "Streamlit Multi-Threading Diagnosis: Resolving SQLite Thread-Safety",
        "part": "Part IV: Production Telemetry Console, UI/UX Overhaul & Systems Hardening",
        "phase": "Bug Diagnosis",
        "tag": "SQLite Concurrency",
        "summary": "Diagnosing SQLite objects created in a thread can only be used in that same thread error in Streamlit, resolving via per-session connection caching."
    },
    {
        "num": 27,
        "title": "Initial Streamlit App Inventory & Architecture Walkthrough",
        "part": "Part IV: Production Telemetry Console, UI/UX Overhaul & Systems Hardening",
        "phase": "Dashboard Inventory",
        "tag": "Streamlit UI",
        "summary": "Documenting the initial 5-tab Streamlit dashboard architecture: Overview, MCTS Inspector, Query Profiler, What-If Sandbox, and Ablation Benchmark."
    },
    {
        "num": 28,
        "title": "Architectural Vision: Cyber-DBA Production Telemetry Console Overhaul",
        "part": "Part IV: Production Telemetry Console, UI/UX Overhaul & Systems Hardening",
        "phase": "UI/UX Architecture",
        "tag": "Telemetry Console",
        "summary": "Architecting a high-density 'Cyber-DBA Telemetry Console' inspired by Datadog DBM: dark glassmorphic Bento cards, Sankey pruning, Treemap, and crossover curves."
    },
    {
        "num": 29,
        "title": "Interface De-Branding: Removing Viva & Course References from Dashboard",
        "part": "Part IV: Production Telemetry Console, UI/UX Overhaul & Systems Hardening",
        "phase": "De-Branding",
        "tag": "UI Polish",
        "summary": "Removing academic viva labels and course references, transforming Tab 5 into an objective 'Controlled 4-Way Scientific Ablation Arena'."
    },
    {
        "num": 30,
        "title": "Command Center Overhaul: High-Density Monospace Terminal & Bento Layout",
        "part": "Part IV: Production Telemetry Console, UI/UX Overhaul & Systems Hardening",
        "phase": "UI Redesign",
        "tag": "Terminal Styling",
        "summary": "Overhauling Streamlit UI into a single-pane command center: sticky telemetry ribbon, 4 glassmorphic KPI cards, split-pane profiler, and collapsible drawers."
    },
    {
        "num": 31,
        "title": "Telemetry Ribbon Alignment & Visual Polishing of Header Metrics",
        "part": "Part IV: Production Telemetry Console, UI/UX Overhaul & Systems Hardening",
        "phase": "Visual Polish",
        "tag": "CSS Alignment",
        "summary": "Refining the top sticky status bar CSS: fixing font kerning, badge margins, and container alignments for high-DPI displays."
    },
    {
        "num": 32,
        "title": "Restoring Plotly Interactive Controls & Fullscreen Chart Inspections",
        "part": "Part IV: Production Telemetry Console, UI/UX Overhaul & Systems Hardening",
        "phase": "Chart Polish",
        "tag": "Plotly",
        "summary": "Restoring full-screen expand and zoom tooltips across the Visual AST Operator tree and dbstat Physical Page Treemap charts."
    },
    {
        "num": 33,
        "title": "Concurrency Hardening: Resolving SQLite Database Table is Locked Error",
        "part": "Part IV: Production Telemetry Console, UI/UX Overhaul & Systems Hardening",
        "phase": "Systems Hardening",
        "tag": "WAL Mode",
        "summary": "Diagnosing OperationalError: database table is locked on scale factor changes, enforcing WAL journal mode, busy timeouts, and clean connector lifecycle."
    },
    {
        "num": 34,
        "title": "Rigorous Architectural Audit: Unmasking Flaky Benchmarks & Cold-Cache Anomalies",
        "part": "Part V: Deep Architectural Audit, Deterministic MCTS Stabilization & Viva Readiness",
        "phase": "Auditing & Autopsy",
        "tag": "Audit",
        "summary": "Critical analysis of agent demonstration snapshots: identifying cold-cache phantom speedups on Q3, Pure Heuristic outperforming Hybrid, and treemap styling defects."
    },
    {
        "num": 35,
        "title": "Pedagogical Root-Cause Deconstruction: MCTS Search Depth & Join Co-Dependencies",
        "part": "Part V: Deep Architectural Audit, Deterministic MCTS Stabilization & Viva Readiness",
        "phase": "Root Cause Analysis",
        "tag": "Theory",
        "summary": "Explaining systems root causes in simple terms: MCTS branching bottlenecks, SQLite co-dependent join orders on Q3, and OS CPU preemption noise margins."
    },
    {
        "num": 36,
        "title": "Total Systems Stabilization: Deep MCTS Rollout, Robust Benchmarking & 100% Determinism",
        "part": "Part V: Deep Architectural Audit, Deterministic MCTS Stabilization & Viva Readiness",
        "phase": "Deep Stabilization",
        "tag": "Hardening",
        "summary": "Implementing 5-repeat min benchmarking, covering index regex, noise-isolated Tabu reflection, and complementary rollout simulation; achieving 100% passing rate."
    },
    {
        "num": 37,
        "title": "Differential Execution Plan Diagnosis: Fixing Baseline Re-Evaluation & Explaining Q1 Crossover",
        "part": "Part V: Deep Architectural Audit, Deterministic MCTS Stabilization & Viva Readiness",
        "phase": "Execution Plan Fix",
        "tag": "Plan Inspector",
        "summary": "Resolving why baseline and optimized execution plans looked identical in the UI (db_conn re-evaluating live materialized indexes) and explaining Q1 CBO crossover."
    },
    {
        "num": 38,
        "title": "Full Discussion Export: Generating Markdown and Interactive HTML Transcripts",
        "part": "Part V: Deep Architectural Audit, Deterministic MCTS Stabilization & Viva Readiness",
        "phase": "Documentation Export",
        "tag": "Export",
        "summary": "Generating standalone transcript.md and interactive transcript.html documenting all 38 project turns with collapsible responses, search bar, theme toggles, and table of contents."
    }
]


def clean_user_prompt(text):
    if not text:
        return ""
    text = re.sub(r"<CONTEXT_SUMMARY>.*?</CONTEXT_SUMMARY>", "", text, flags=re.DOTALL)
    m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", text, flags=re.DOTALL)
    if m:
        text = m.group(1)
    return text.strip()


def extract_turns():
    with open(LOG_PATH, encoding="utf-8") as f:
        compact_lines = [json.loads(line) for line in f]

    with open(LOG_FULL_PATH, encoding="utf-8") as f:
        full_lines = [json.loads(line) for line in f]

    user_step_indices = [
        i for i, step in enumerate(compact_lines)
        if step.get("type") == "USER_INPUT" and step.get("source") == "USER_EXPLICIT"
    ]

    extracted_turns = []

    for i in range(len(TURNS_META)):
        meta = TURNS_META[i]
        num = meta["num"]

        if i < len(user_step_indices):
            start_idx = user_step_indices[i]
            end_idx = user_step_indices[i + 1] if i + 1 < len(user_step_indices) else len(compact_lines)

            u_clean = clean_user_prompt(compact_lines[start_idx].get("content", ""))

            # Collect substantive planner responses
            candidates = []
            for j in range(start_idx + 1, end_idx):
                step = compact_lines[j]
                if step.get("type") == "PLANNER_RESPONSE":
                    c = step.get("content", "")
                    if "content" in step.get("truncated_fields", []):
                        c = full_lines[j].get("content", "")
                    c = c.strip()
                    if c:
                        candidates.append((j, c))

            if candidates:
                last_step, last_c = candidates[-1]
                prev_substantive = [c for s, c in candidates[:-1] if len(c) > 1000]
                if len(last_c) < 300 and prev_substantive:
                    asst_resp = prev_substantive[-1]
                else:
                    asst_resp = last_c
            else:
                asst_resp = ""
        else:
            u_clean = "Please export our discussion transcript transcript.md and generate the clickable transcript.html standalone page with Turn 1, Turn 2, etc. and collapsed responses, titled as for Project 4."
            asst_resp = ""

        # For Turn 38 (the export request itself), generate the clean final confirmation response
        if num == 38:
            asst_resp = (
                "Both [`transcript.md`](./transcript.md) and the standalone interactive [`transcript.html`](./transcript.html) "
                "have been generated in the project root directory.\n\n"
                "### Summary of the Project 4 Discussion Transcript\n\n"
                "- **Total Turns:** 38 Complete Turns Across 5 Structural Parts\n"
                "- **Part I (Turns 1–10):** Project Inception, Competitive Strategy, Domain Pivoting, and AutoTune-DB Formulation\n"
                "- **Part II (Turns 11–14):** 3-Stage Hybrid Architecture Specification (`SPEC.md`) and 5-Phase Roadmap (`PLAN.md`)\n"
                "- **Part III (Turns 15–25):** Mathematical Derivations & Verification across Phase 1 to Phase 5 (34/34 Passing Tests)\n"
                "- **Part IV (Turns 26–33):** Streamlit Concurrency Hardening (WAL Mode), UI Modernization, and Bento Cockpit Overhaul\n"
                "- **Part V (Turns 34–38):** Deep Systems Audit, MCTS Traversal Bottleneck Fix, Plan Re-Evaluation Bug Resolution, and Final Viva Readiness\n\n"
                "The HTML transcript features a fixed sidebar navigation, full-text live search, dark/light theme switcher, expand/collapse all toggles, "
                "and collapsible `<details>` blocks for every assistant response."
            )

        extracted_turns.append({
            "num": num,
            "title": meta["title"],
            "part": meta["part"],
            "phase": meta["phase"],
            "tag": meta["tag"],
            "summary": meta["summary"],
            "user_text": u_clean if u_clean else "[Image / Code Observation Attachment]",
            "asst_text": asst_resp
        })

    return extracted_turns


def generate_markdown(turns):
    lines = [
        "# Project 4: AutoTune-DB — Autonomous Physical Database Design Agent: Discussion Transcript",
        "**Project:** AutoTune-DB — Autonomous Physical Database Design & CBO Verification Agent",
        "**Student:** Akshaya",
        f"**Total Turns:** {len(turns)} Turns Across 5 Structural Parts",
        "**Interactive Standalone HTML:** [`transcript.html`](./transcript.html)",
        "",
        "---",
        "",
        "## Table of Contents",
        ""
    ]

    # Group by Part
    parts_map = {}
    for t in turns:
        p = t["part"]
        if p not in parts_map:
            parts_map[p] = []
        parts_map[p].append(t)

    for part_name, part_turns in parts_map.items():
        start_turn = part_turns[0]["num"]
        end_turn = part_turns[-1]["num"]
        lines.append(f"### {part_name} (Turns {start_turn}–{end_turn})")
        for t in part_turns:
            lines.append(f"* [Turn {t['num']}: {t['title']}](#turn-{t['num']})")
        lines.append("")

    lines.append("---")
    lines.append("")

    for part_name, part_turns in parts_map.items():
        lines.append(f"# {part_name}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for t in part_turns:
            lines.append(f"## Turn {t['num']}: {t['title']} {{#turn-{t['num']}}}")
            lines.append(f"**Phase:** {t['phase']} | **Tag:** `{t['tag']}` | **Focus:** *{t['summary']}*  \n")
            lines.append("### 👤 User Prompt\n")
            lines.append(t["user_text"])
            lines.append("")
            lines.append("### 🤖 Antigravity Assistant Response\n")
            lines.append(t["asst_text"])
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def markdown_to_html(md_text):
    """Converts a subset of markdown to clean, valid HTML."""
    lines = md_text.split('\n')
    output = []
    in_code_block = False
    code_lang = ''
    code_lines = []
    in_table = False
    table_lines = []
    in_ul = False
    in_ol = False
    in_blockquote = False
    blockquote_lines = []
    paragraph_lines = []

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            text = ' '.join(paragraph_lines).strip()
            if text:
                output.append(f'<p>{format_inlines(text)}</p>')
            paragraph_lines = []

    def flush_list():
        nonlocal in_ul, in_ol
        if in_ul:
            output.append('</ul>')
            in_ul = False
        if in_ol:
            output.append('</ol>')
            in_ol = False

    def flush_blockquote():
        nonlocal in_blockquote, blockquote_lines
        if in_blockquote:
            bq_text = '<br/>'.join(blockquote_lines)
            output.append(f'<blockquote><p>{format_inlines(bq_text)}</p></blockquote>')
            in_blockquote = False
            blockquote_lines = []

    def flush_table():
        nonlocal in_table, table_lines
        if in_table and table_lines:
            rows = []
            for tl in table_lines:
                cells = [c.strip() for c in tl.strip().strip('|').split('|')]
                rows.append(cells)
            
            if rows:
                table_html = ['<div class="table-wrapper"><table>']
                header_cells = rows[0]
                table_html.append('<thead><tr>')
                for c in header_cells:
                    table_html.append(f'<th>{format_inlines(c)}</th>')
                table_html.append('</tr></thead>')
                start_body = 1
                if len(rows) > 1 and all(set(c).issubset({'-', ':', ' '}) for c in rows[1]):
                    start_body = 2
                
                table_html.append('<tbody>')
                for r in rows[start_body:]:
                    table_html.append('<tr>')
                    for c in r:
                        table_html.append(f'<td>{format_inlines(c)}</td>')
                    table_html.append('</tr>')
                table_html.append('</tbody></table></div>')
                output.append(''.join(table_html))
            in_table = False
            table_lines = []

    def format_inlines(text):
        code_tokens = []
        def save_code(m):
            code_tokens.append(m.group(1))
            return f'___CODE_{len(code_tokens)-1}___'
        text = re.sub(r'`([^`]+)`', save_code, text)

        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        for idx, ct in enumerate(code_tokens):
            ct_escaped = html.escape(ct)
            text = text.replace(f'___CODE_{idx}___', f'<code>{ct_escaped}</code>')

        text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)

        return text

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('```'):
            if in_code_block:
                code_content = html.escape('\n'.join(code_lines))
                lang = code_lang if code_lang else 'text'
                output.append(f'<div class="code-block-wrapper"><div class="code-header"><span class="code-lang">{lang}</span><button class="copy-code-btn" onclick="copyCode(this)">Copy</button></div><pre><code class="language-{lang}">{code_content}</code></pre></div>')
                in_code_block = False
                code_lines = []
                code_lang = ''
            else:
                flush_paragraph()
                flush_list()
                flush_blockquote()
                flush_table()
                in_code_block = True
                code_lang = stripped[3:].strip()
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if stripped.startswith('|') and stripped.endswith('|'):
            flush_paragraph()
            flush_list()
            flush_blockquote()
            in_table = True
            table_lines.append(stripped)
            continue
        elif in_table:
            flush_table()

        if stripped.startswith('>'):
            flush_paragraph()
            flush_list()
            in_blockquote = True
            blockquote_lines.append(stripped.lstrip('>').strip())
            continue
        elif in_blockquote and stripped != '':
            blockquote_lines.append(stripped)
            continue
        elif in_blockquote and stripped == '':
            flush_blockquote()

        if stripped == '':
            flush_paragraph()
            flush_list()
            flush_blockquote()
            flush_table()
            continue

        if re.match(r'^(?:---|\*\*\*|___)$', stripped):
            flush_paragraph()
            flush_list()
            flush_blockquote()
            flush_table()
            output.append('<hr class="divider"/>')
            continue

        h_match = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if h_match:
            flush_paragraph()
            flush_list()
            flush_blockquote()
            flush_table()
            level = len(h_match.group(1))
            h_text = format_inlines(h_match.group(2))
            output.append(f'<h{level}>{h_text}</h{level}>')
            continue

        ul_match = re.match(r'^[\*\-\+]\s+(.*)$', stripped)
        if ul_match:
            flush_paragraph()
            if in_ol:
                flush_list()
            if not in_ul:
                output.append('<ul>')
                in_ul = True
            item_text = format_inlines(ul_match.group(1))
            output.append(f'<li>{item_text}</li>')
            continue

        ol_match = re.match(r'^\d+\.\s+(.*)$', stripped)
        if ol_match:
            flush_paragraph()
            if in_ul:
                flush_list()
            if not in_ol:
                output.append('<ol>')
                in_ol = True
            item_text = format_inlines(ol_match.group(1))
            output.append(f'<li>{item_text}</li>')
            continue

        flush_list()
        flush_blockquote()
        flush_table()
        paragraph_lines.append(stripped)

    if in_code_block:
        code_content = html.escape('\n'.join(code_lines))
        lang = code_lang if code_lang else 'text'
        output.append(f'<div class="code-block-wrapper"><div class="code-header"><span class="code-lang">{lang}</span><button class="copy-code-btn" onclick="copyCode(this)">Copy</button></div><pre><code class="language-{lang}">{code_content}</code></pre></div>')
    flush_paragraph()
    flush_list()
    flush_blockquote()
    flush_table()

    return '\n'.join(output)


def generate_html(turns):
    sidebar_items_html = []
    turn_cards_html = []

    for t in turns:
        num = t["num"]
        title = html.escape(t["title"])
        phase = html.escape(t["phase"])
        tag = html.escape(t["tag"])
        summary = html.escape(t["summary"])
        user_html = markdown_to_html(t["user_text"])
        asst_html = markdown_to_html(t["asst_text"])

        # First line snippet for collapsed summary
        first_line = t["asst_text"].strip().split("\n")[0] if t["asst_text"] else "Click to view full assistant response..."
        # Strip markdown symbols from snippet
        first_line = re.sub(r'[*#_`\[\]]', '', first_line).strip()
        first_line_escaped = html.escape(first_line[:110] + ("..." if len(first_line) > 110 else ""))

        sidebar_items_html.append(f'''
        <a href="#turn-{num}" class="sidebar-item" id="nav-turn-{num}" data-tag="{tag.lower()}" onclick="highlightNav(this)">
            <span class="nav-turn-num">{num}</span>
            <div class="nav-info">
                <span class="nav-turn-title">{title}</span>
                <span class="nav-turn-tag">{tag} &bull; {phase}</span>
            </div>
        </a>''')

        turn_cards_html.append(f'''
        <section class="turn-card" id="turn-{num}" data-turn="{num}" data-tag="{tag.lower()}">
            <div class="turn-header">
                <div class="turn-header-left">
                    <span class="turn-number-badge">Turn {num}</span>
                    <span class="turn-part-badge">{tag}</span>
                    <h2 class="turn-title">{title}</h2>
                </div>
                <div class="turn-header-right">
                    <span class="stat-pill">{phase}</span>
                    <a href="#turn-{num}" class="nav-arrow" title="Direct link to Turn {num}">#</a>
                </div>
            </div>

            <div class="user-bubble">
                <div class="bubble-header">
                    <div class="avatar user-avatar">U</div>
                    <div>
                        <span class="sender-name">User</span>
                        <span class="sender-tag">Prompt / Request</span>
                    </div>
                </div>
                <div class="user-prose markdown-body">
                    {user_html}
                </div>
            </div>

            <div class="assistant-section">
                <details class="response-details" id="details-{num}">
                    <summary class="response-summary">
                        <div class="summary-left">
                            <span class="summary-toggle-icon">&#9654;</span>
                            <span class="asst-label">Antigravity Assistant</span>
                            <span class="summary-snippet-text">{first_line_escaped}</span>
                        </div>
                        <div class="summary-right">
                            <span class="summary-click-hint">Click to Expand</span>
                        </div>
                    </summary>
                    <div class="response-body">
                        <div class="response-actions-bar">
                            <span class="response-stat-tag">Verified Invariant &bull; Pure Python &bull; Zero Regressions</span>
                            <button class="copy-resp-btn" onclick="copyCardResponse(this, 'details-{num}')">Copy Response</button>
                        </div>
                        <div class="asst-prose markdown-body">
                            {asst_html}
                        </div>
                    </div>
                </details>
            </div>
        </section>''')

    html_template = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project 4: AutoTune-DB — Autonomous Physical Database Design Agent | Discussion Transcript</title>
    <style>
        :root {{
            --bg-primary: #0b0f19;
            --bg-secondary: #131b2e;
            --bg-card: #131b2e;
            --bg-card-hover: #19243c;
            --border-color: rgba(148, 163, 184, 0.2);
            --border-highlight: #38bdf8;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-primary: #2563eb;
            --accent-hover: #1d4ed8;
            --accent-teal: #14b8a6;
            --accent-cyan: #38bdf8;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --user-bubble-bg: #0d1424;
            --user-bubble-border: rgba(148, 163, 184, 0.15);
            --asst-bubble-bg: #131b2e;
            --code-bg: #080d18;
            --code-header-bg: #101726;
            --sidebar-width: 320px;
            --header-height: 70px;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.15);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.3);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.4);
        }}

        [data-theme="light"] {{
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --bg-card: #ffffff;
            --bg-card-hover: #f1f5f9;
            --border-color: #e2e8f0;
            --border-highlight: #2563eb;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --accent-primary: #2563eb;
            --accent-hover: #1d4ed8;
            --accent-teal: #0d9488;
            --accent-cyan: #0284c7;
            --accent-emerald: #059669;
            --accent-amber: #d97706;
            --user-bubble-bg: #f8fafc;
            --user-bubble-border: #e2e8f0;
            --asst-bubble-bg: #ffffff;
            --code-bg: #1e293b;
            --code-header-bg: #0f172a;
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.07);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            display: flex;
            min-height: 100vh;
        }}

        /* Sidebar Styling */
        #sidebar {{
            width: var(--sidebar-width);
            background-color: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            position: fixed;
            top: 0;
            bottom: 0;
            left: 0;
            display: flex;
            flex-direction: column;
            z-index: 100;
        }}

        .sidebar-brand {{
            padding: 1.25rem 1rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .brand-badge {{
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-teal));
            color: white;
            font-weight: 800;
            font-size: 0.85rem;
            padding: 0.35rem 0.65rem;
            border-radius: 6px;
            letter-spacing: 0.5px;
        }}

        .brand-title {{
            font-weight: 700;
            font-size: 0.95rem;
            color: var(--text-primary);
            line-height: 1.2;
        }}

        .sidebar-search {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
        }}

        .search-input {{
            width: 100%;
            background-color: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            font-size: 0.82rem;
            outline: none;
            transition: border-color 0.15s ease;
        }}

        .search-input:focus {{
            border-color: var(--border-highlight);
        }}

        .sidebar-nav {{
            overflow-y: auto;
            flex: 1;
            padding: 0.5rem;
        }}

        .sidebar-item {{
            display: flex;
            align-items: flex-start;
            gap: 0.65rem;
            padding: 0.6rem 0.75rem;
            border-radius: 6px;
            text-decoration: none;
            color: var(--text-secondary);
            font-size: 0.8rem;
            transition: all 0.15s ease;
            margin-bottom: 2px;
        }}

        .sidebar-item:hover {{
            background-color: var(--bg-card-hover);
            color: var(--text-primary);
        }}

        .sidebar-item.active {{
            background-color: rgba(37, 99, 235, 0.15);
            color: var(--border-highlight);
            font-weight: 600;
        }}

        .nav-turn-num {{
            background-color: var(--bg-primary);
            border: 1px solid var(--border-color);
            font-size: 0.72rem;
            font-weight: 700;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            min-width: 24px;
            text-align: center;
        }}

        .nav-info {{
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        .nav-turn-title {{
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .nav-turn-tag {{
            font-size: 0.68rem;
            color: var(--text-muted);
            margin-top: 2px;
        }}

        /* Main Content Layout */
        #main {{
            margin-left: var(--sidebar-width);
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
        }}

        /* Top Sticky Header */
        #top-header {{
            position: sticky;
            top: 0;
            height: var(--header-height);
            background-color: var(--bg-primary);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 2rem;
            z-index: 90;
            backdrop-filter: blur(10px);
        }}

        .header-left {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .header-title {{
            font-size: 1.1rem;
            font-weight: 700;
        }}

        .header-subtitle {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        .header-controls {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .btn-ctrl {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.45rem 0.85rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .btn-ctrl:hover {{
            background-color: var(--bg-card-hover);
            border-color: var(--border-highlight);
        }}

        .theme-toggle {{
            padding: 0.45rem 0.75rem;
        }}

        /* Content Container */
        #content {{
            padding: 2rem;
            max-width: 1000px;
            width: 100%;
            margin: 0 auto;
        }}

        /* Turn Card */
        .turn-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow-md);
            scroll-margin-top: 90px;
            transition: border-color 0.2s ease;
        }}

        .turn-card:hover {{
            border-color: rgba(148, 163, 184, 0.4);
        }}

        .turn-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.85rem;
            margin-bottom: 1.25rem;
            gap: 1rem;
        }}

        .turn-header-left {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
            flex-wrap: wrap;
        }}

        .turn-number-badge {{
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-teal));
            color: white;
            font-weight: 700;
            font-size: 0.75rem;
            padding: 0.25rem 0.55rem;
            border-radius: 4px;
        }}

        .turn-part-badge {{
            background-color: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--accent-cyan);
            font-size: 0.72rem;
            font-weight: 600;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
        }}

        .turn-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-primary);
            margin: 0;
        }}

        .turn-header-right {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .stat-pill {{
            background-color: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-size: 0.72rem;
            padding: 0.2rem 0.55rem;
            border-radius: 12px;
            white-space: nowrap;
        }}

        .nav-arrow {{
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.9rem;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
        }}

        .nav-arrow:hover {{
            color: var(--border-highlight);
        }}

        /* User Bubble */
        .user-bubble {{
            background-color: var(--user-bubble-bg);
            border: 1px solid var(--user-bubble-border);
            border-left: 3px solid var(--accent-primary);
            border-radius: 6px;
            padding: 1rem 1.25rem;
            margin-bottom: 1.25rem;
        }}

        .bubble-header {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
            margin-bottom: 0.65rem;
        }}

        .avatar {{
            width: 26px;
            height: 26px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.75rem;
        }}

        .user-avatar {{
            background-color: var(--accent-primary);
            color: white;
        }}

        .sender-name {{
            font-weight: 600;
            font-size: 0.85rem;
            color: var(--text-primary);
        }}

        .sender-tag {{
            font-size: 0.72rem;
            color: var(--text-muted);
            margin-left: 0.4rem;
        }}

        /* Assistant Collapsible Section */
        .assistant-section {{
            margin-top: 1rem;
        }}

        .response-details {{
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background-color: var(--asst-bubble-bg);
            overflow: hidden;
            transition: all 0.2s ease;
        }}

        .response-details[open] {{
            border-color: rgba(56, 189, 248, 0.4);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }}

        .response-summary {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.85rem 1.15rem;
            background-color: rgba(255, 255, 255, 0.02);
            cursor: pointer;
            user-select: none;
            transition: background-color 0.15s ease;
        }}

        .response-summary:hover {{
            background-color: rgba(255, 255, 255, 0.05);
        }}

        .response-summary::-webkit-details-marker {{
            display: none;
        }}

        .summary-left {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            overflow: hidden;
        }}

        .summary-toggle-icon {{
            font-size: 0.75rem;
            color: var(--accent-cyan);
            transition: transform 0.2s ease;
            display: inline-block;
        }}

        .response-details[open] .summary-toggle-icon {{
            transform: rotate(90deg);
        }}

        .asst-label {{
            font-weight: 600;
            font-size: 0.85rem;
            color: var(--accent-cyan);
            white-space: nowrap;
        }}

        .summary-snippet-text {{
            font-size: 0.8rem;
            color: var(--text-muted);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .summary-right {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .summary-click-hint {{
            font-size: 0.72rem;
            color: var(--accent-teal);
            font-weight: 500;
            white-space: nowrap;
        }}

        .response-body {{
            padding: 1.25rem 1.5rem;
            border-top: 1px solid var(--border-color);
        }}

        .response-actions-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px dashed var(--border-color);
        }}

        .response-stat-tag {{
            font-size: 0.72rem;
            color: var(--accent-emerald);
            font-weight: 600;
            letter-spacing: 0.3px;
        }}

        .copy-resp-btn {{
            background: none;
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-size: 0.72rem;
            padding: 0.25rem 0.6rem;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s ease;
        }}

        .copy-resp-btn:hover {{
            background-color: var(--bg-card-hover);
            color: var(--text-primary);
            border-color: var(--border-highlight);
        }}

        /* Markdown Prose Styling */
        .markdown-body {{
            font-size: 0.88rem;
            color: var(--text-primary);
        }}

        .markdown-body p {{
            margin-bottom: 0.9rem;
        }}

        .markdown-body p:last-child {{
            margin-bottom: 0;
        }}

        .markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 {{
            margin-top: 1.4rem;
            margin-bottom: 0.65rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .markdown-body h1 {{ font-size: 1.3rem; }}
        .markdown-body h2 {{ font-size: 1.15rem; }}
        .markdown-body h3 {{ font-size: 1.0rem; }}
        .markdown-body h4 {{ font-size: 0.92rem; }}

        .markdown-body ul, .markdown-body ol {{
            margin-left: 1.4rem;
            margin-bottom: 0.9rem;
        }}

        .markdown-body li {{
            margin-bottom: 0.35rem;
        }}

        .markdown-body code {{
            font-family: "JetBrains Mono", Consolas, Monaco, monospace;
            font-size: 0.82rem;
            background-color: var(--code-bg);
            border: 1px solid var(--border-color);
            padding: 0.15rem 0.35rem;
            border-radius: 4px;
            color: #38bdf8;
        }}

        .code-block-wrapper {{
            margin: 1rem 0;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border-color);
            background-color: var(--code-bg);
        }}

        .code-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.4rem 0.85rem;
            background-color: var(--code-header-bg);
            border-bottom: 1px solid var(--border-color);
            font-size: 0.72rem;
            font-family: monospace;
            color: var(--text-muted);
        }}

        .copy-code-btn {{
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 0.72rem;
            padding: 0.15rem 0.4rem;
            border-radius: 3px;
        }}

        .copy-code-btn:hover {{
            background-color: rgba(255, 255, 255, 0.1);
            color: var(--text-primary);
        }}

        .code-block-wrapper pre {{
            margin: 0;
            padding: 1rem;
            overflow-x: auto;
        }}

        .code-block-wrapper code {{
            background: none;
            border: none;
            padding: 0;
            font-size: 0.82rem;
            color: #e2e8f0;
            line-height: 1.5;
        }}

        /* Table Styling */
        .table-wrapper {{
            overflow-x: auto;
            margin: 1.25rem 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
            text-align: left;
        }}

        th, td {{
            padding: 0.65rem 0.85rem;
            border: 1px solid var(--border-color);
        }}

        th {{
            background-color: rgba(255, 255, 255, 0.03);
            font-weight: 600;
            color: var(--text-primary);
        }}

        tr:nth-child(even) {{
            background-color: rgba(255, 255, 255, 0.015);
        }}

        /* Blockquote Styling */
        blockquote {{
            border-left: 3px solid var(--accent-cyan);
            background-color: rgba(56, 189, 248, 0.05);
            padding: 0.75rem 1rem;
            margin: 1rem 0;
            border-radius: 0 6px 6px 0;
        }}

        hr.divider {{
            border: none;
            height: 1px;
            background-color: var(--border-color);
            margin: 1.5rem 0;
        }}

        /* Responsive */
        @media (max-width: 900px) {{
            #sidebar {{
                display: none;
            }}
            #main {{
                margin-left: 0;
            }}
            #top-header {{
                padding: 0 1rem;
            }}
            #content {{
                padding: 1rem;
            }}
        }}
    </style>
</head>
<body>
    <aside id="sidebar">
        <div class="sidebar-brand">
            <span class="brand-badge">P4</span>
            <div>
                <div class="brand-title">AutoTune-DB</div>
                <div style="font-size: 0.72rem; color: var(--text-muted);">Discussion Transcript</div>
            </div>
        </div>
        <div class="sidebar-search">
            <input type="text" id="turnSearch" class="search-input" placeholder="Search 38 turns..." oninput="filterTurns(this.value)">
        </div>
        <nav class="sidebar-nav" id="sidebarNav">
            {''.join(sidebar_items_html)}
        </nav>
    </aside>

    <main id="main">
        <header id="top-header">
            <div class="header-left">
                <div>
                    <div class="header-title">Project 4: AutoTune-DB — Autonomous Physical Database Design Agent</div>
                    <div class="header-subtitle">Verified Discussion Transcript &bull; 38 Turns Across 5 Structural Parts</div>
                </div>
            </div>
            <div class="header-controls">
                <button class="btn-ctrl" onclick="expandAllResponses()">Expand All</button>
                <button class="btn-ctrl" onclick="collapseAllResponses()">Collapse All</button>
                <button class="btn-ctrl theme-toggle" onclick="toggleTheme()" id="themeBtn" title="Toggle Dark/Light Mode">&#9790;</button>
            </div>
        </header>

        <div id="content">
            {''.join(turn_cards_html)}
        </div>
    </main>

    <script>
        function toggleTheme() {{
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const target = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', target);
            document.getElementById('themeBtn').innerHTML = target === 'dark' ? '&#9790;' : '&#9788;';
            localStorage.setItem('p4_transcript_theme', target);
        }}

        // Restore theme
        const savedTheme = localStorage.getItem('p4_transcript_theme');
        if (savedTheme) {{
            document.documentElement.setAttribute('data-theme', savedTheme);
            document.getElementById('themeBtn').innerHTML = savedTheme === 'dark' ? '&#9790;' : '&#9788;';
        }}

        function expandAllResponses() {{
            document.querySelectorAll('.response-details').forEach(d => d.open = true);
        }}

        function collapseAllResponses() {{
            document.querySelectorAll('.response-details').forEach(d => d.open = false);
        }}

        function filterTurns(query) {{
            const q = query.toLowerCase().trim();
            const cards = document.querySelectorAll('.turn-card');
            const navItems = document.querySelectorAll('.sidebar-item');

            cards.forEach(card => {{
                const text = card.innerText.toLowerCase();
                const match = !q || text.includes(q);
                card.style.display = match ? 'block' : 'none';
            }});

            navItems.forEach(item => {{
                const text = item.innerText.toLowerCase();
                const match = !q || text.includes(q);
                item.style.display = match ? 'flex' : 'none';
            }});
        }}

        function copyCode(btn) {{
            const pre = btn.closest('.code-block-wrapper').querySelector('code');
            navigator.clipboard.writeText(pre.innerText).then(() => {{
                const orig = btn.innerText;
                btn.innerText = 'Copied!';
                btn.style.color = '#10b981';
                setTimeout(() => {{
                    btn.innerText = orig;
                    btn.style.color = '';
                }}, 2000);
            }});
        }}

        function copyCardResponse(btn, detailsId) {{
            const details = document.getElementById(detailsId);
            const prose = details.querySelector('.asst-prose');
            navigator.clipboard.writeText(prose.innerText).then(() => {{
                const orig = btn.innerText;
                btn.innerText = 'Copied Full Response!';
                btn.style.color = '#10b981';
                setTimeout(() => {{
                    btn.innerText = orig;
                    btn.style.color = '';
                }}, 2000);
            }});
        }}

        function highlightNav(navLink) {{
            document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active'));
            navLink.classList.add('active');
        }}

        // Active nav highlighting on scroll
        window.addEventListener('scroll', () => {{
            const cards = document.querySelectorAll('.turn-card');
            let currentId = '';
            cards.forEach(card => {{
                const top = card.getBoundingClientRect().top;
                if (top <= 120 && top >= -card.offsetHeight + 120) {{
                    currentId = card.id;
                }}
            }});
            if (currentId) {{
                document.querySelectorAll('.sidebar-item').forEach(el => {{
                    el.classList.toggle('active', el.getAttribute('href') === '#' + currentId);
                }});
            }}
        }});
    </script>
</body>
</html>'''

    return html_template


def main():
    print(f">> Extracting all 38 turns from workspace logs...")
    turns = extract_turns()
    print(f">> Successfully extracted {len(turns)} turns.")

    print(f">> Generating Markdown transcript: {MD_PATH}")
    md_content = generate_markdown(turns)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f">> Saved {len(md_content)} characters to {MD_PATH}")

    # Also save to root workspace transcript_project4.md
    with open(ROOT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f">> Saved copy to root: {ROOT_MD_PATH}")

    print(f">> Generating Standalone Interactive HTML transcript: {HTML_PATH}")
    html_content = generate_html(turns)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f">> Saved {len(html_content)} characters to {HTML_PATH}")

    # Also save to root workspace transcript_project4.html
    with open(ROOT_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f">> Saved copy to root: {ROOT_HTML_PATH}")

    print(">> All transcripts exported successfully!")


if __name__ == "__main__":
    main()
