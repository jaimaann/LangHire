#!/usr/bin/env python3
"""
Agent Performance Dashboard — tracks accuracy, speed, and memory impact.

Usage:
  uv run python dashboard.py                    # Full dashboard
  uv run python dashboard.py --backfill         # Backfill metrics from historical logs first
  uv run python dashboard.py --json             # Output as JSON
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.memory import MemoryStore
from backend.memory.metrics import MetricsStore

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


# ── Terminal colors (ANSI) ───────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def bar(value: float, max_value: float = 100, width: int = 20) -> str:
    """ASCII progress bar."""
    filled = int(value / max_value * width) if max_value > 0 else 0
    filled = min(filled, width)
    color = GREEN if value >= 70 else YELLOW if value >= 40 else RED
    return f"{color}{'█' * filled}{'░' * (width - filled)}{RESET} {value:.1f}%"


def spark(values: list[float]) -> str:
    """Sparkline chart from a list of values."""
    if not values:
        return ""
    sparks = "▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    return "".join(sparks[min(int((v - mn) / rng * 7), 7)] for v in values)


# ── Backfill from historical logs ────────────────────────────────────────────

def backfill_metrics_from_logs(metrics: MetricsStore, mem_store: MemoryStore):
    """Parse historical logs and backfill run_metrics table."""
    from memory_backfill import get_sorted_log_files, extract_job_url, extract_job_title_company, parse_agent_json

    log_dirs = sorted([
        d for d in LOGS_DIR.iterdir()
        if d.is_dir() and d.name.startswith("apply_")
    ])

    if not log_dirs:
        print("No log directories found.")
        return

    # Check what's already recorded
    existing = {r["job_url"] for r in metrics.get_all_runs(limit=10000)}
    new_count = 0

    for log_dir in log_dirs:
        files = get_sorted_log_files(log_dir)
        if not files:
            continue

        job_url = extract_job_url(files[0])
        if job_url in existing:
            continue

        job_title, company = extract_job_title_company(files[0])

        # Parse last file for success/done
        last_text = files[-1].read_text(errors="replace")
        last_json = parse_agent_json(last_text)
        success = False
        error_msg = None
        if last_json:
            for action in last_json.get("action", []):
                if isinstance(action, dict) and "done" in action:
                    success = action["done"].get("success", False)
                    if not success:
                        error_msg = (action["done"].get("text", "") or "")[:200]
                    break

        # Extract domains visited
        domains = set()
        for f in [files[0], files[-1]]:
            text = f.read_text(errors="replace")
            for m in re.finditer(r"Tab \w+:\s*(https?://[^\s]+)\s*-", text):
                try:
                    host = urlparse(m.group(1)).hostname or ""
                    if host.startswith("www."):
                        host = host[4:]
                    if host:
                        domains.add(mem_store.normalize_domain(host.lower()))
                except Exception:
                    pass

        # Primary domain = first non-linkedin domain, or linkedin
        domain = "linkedin.com"
        for d in sorted(domains):
            if "linkedin.com" not in d and "google.com" not in d:
                domain = d
                break

        ats = mem_store.detect_ats_platform(domain)

        # Use file timestamps for timing
        try:
            first_mtime = datetime.fromtimestamp(files[0].stat().st_mtime, tz=timezone.utc)
            last_mtime = datetime.fromtimestamp(files[-1].stat().st_mtime, tz=timezone.utc)
        except Exception:
            first_mtime = datetime.now(timezone.utc)
            last_mtime = first_mtime

        metrics.record_run(
            job_url=job_url,
            job_title=job_title,
            company=company,
            website_domain=domain,
            ats_platform=ats,
            success=success,
            started_at=first_mtime,
            finished_at=last_mtime,
            step_count=len(files),
            memories_injected=0,  # Historical runs had no memory system
            memories_extracted=0,
            error_message=error_msg,
            run_type="apply_historical",
        )
        new_count += 1

    if new_count:
        print(f"📊 Backfilled {new_count} historical runs into metrics")
    else:
        print("📊 All historical runs already recorded")


# ── Dashboard display ────────────────────────────────────────────────────────

def print_dashboard(metrics: MetricsStore, mem_store: MemoryStore):
    """Print the full performance dashboard."""
    overall = metrics.get_overall_stats()
    domain_stats = metrics.get_domain_stats()
    impact = metrics.get_memory_impact()
    trend = metrics.get_trend(window_size=5)
    mem_stats = mem_store.get_stats()

    print(f"\n{BOLD}{'═' * 70}{RESET}")
    print(f"{BOLD}  🧠 AGENT PERFORMANCE DASHBOARD{RESET}")
    print(f"{BOLD}{'═' * 70}{RESET}")

    if not overall.get("total_runs"):
        print(f"\n  {DIM}No runs recorded yet. Run applications or use --backfill to import historical data.{RESET}\n")
        return

    # ── Overall Stats ─────────────────────────────────────────────────────
    print(f"\n{BOLD}  📊 OVERALL METRICS{RESET}")
    print(f"  {'─' * 50}")

    total = overall["total_runs"]
    succ = overall["successes"] or 0
    fail = overall["failures"] or 0
    rate = overall["success_rate"] or 0

    print(f"  Total Runs:        {total}")
    print(f"  Success Rate:      {bar(rate)}")
    print(f"  Successes:         {GREEN}{succ}{RESET}  |  Failures: {RED}{fail}{RESET}")
    print(f"  Avg Duration:      {overall['avg_duration']}s")
    print(f"  Avg Steps/Run:     {overall['avg_steps']}")
    if overall.get("total_cost"):
        print(f"  Total Cost:        ${overall['total_cost']:.4f}")
    print(f"  Period:            {(overall.get('first_run') or '')[:10]} → {(overall.get('last_run') or '')[:10]}")

    # ── Memory System Stats ───────────────────────────────────────────────
    print(f"\n{BOLD}  🧠 MEMORY SYSTEM{RESET}")
    print(f"  {'─' * 50}")
    print(f"  Total Memories:    {mem_stats['total_memories']}")
    print(f"  Unique Domains:    {mem_stats['unique_domains']}")
    if mem_stats.get("by_category"):
        cats = ", ".join(f"{k}: {v}" for k, v in sorted(mem_stats["by_category"].items(), key=lambda x: -x[1]))
        print(f"  Categories:        {cats}")

    # ── Memory Impact (A/B Comparison) ────────────────────────────────────
    w = impact.get("with_memory", {})
    wo = impact.get("without_memory", {})

    if w.get("runs") and wo.get("runs"):
        print(f"\n{BOLD}  ⚡ MEMORY IMPACT (A/B){RESET}")
        print(f"  {'─' * 50}")
        print(f"  {'Metric':<25} {'Without Memory':>15} {'With Memory':>15} {'Delta':>10}")
        print(f"  {'─' * 65}")

        wo_rate = wo.get("success_rate", 0) or 0
        w_rate = w.get("success_rate", 0) or 0
        delta_rate = w_rate - wo_rate
        delta_color = GREEN if delta_rate > 0 else RED if delta_rate < 0 else DIM
        print(f"  {'Success Rate':<25} {wo_rate:>14.1f}% {w_rate:>14.1f}% {delta_color}{delta_rate:>+9.1f}%{RESET}")

        wo_dur = wo.get("avg_duration", 0) or 0
        w_dur = w.get("avg_duration", 0) or 0
        delta_dur = w_dur - wo_dur
        delta_color = GREEN if delta_dur < 0 else RED if delta_dur > 0 else DIM
        print(f"  {'Avg Duration (s)':<25} {wo_dur:>15.1f} {w_dur:>15.1f} {delta_color}{delta_dur:>+10.1f}{RESET}")

        wo_steps = wo.get("avg_steps", 0) or 0
        w_steps = w.get("avg_steps", 0) or 0
        delta_steps = w_steps - wo_steps
        delta_color = GREEN if delta_steps < 0 else RED if delta_steps > 0 else DIM
        print(f"  {'Avg Steps':<25} {wo_steps:>15.1f} {w_steps:>15.1f} {delta_color}{delta_steps:>+10.1f}{RESET}")

        print(f"\n  Runs without memory: {wo.get('runs', 0)}  |  Runs with memory: {w.get('runs', 0)}")
    elif wo.get("runs"):
        print(f"\n{BOLD}  ⚡ MEMORY IMPACT{RESET}")
        print(f"  {'─' * 50}")
        print(f"  {DIM}All {wo['runs']} runs so far were WITHOUT memory injection.")
        print(f"  Future runs will use the memory system — compare then!{RESET}")

    # ── Per-Domain Breakdown ──────────────────────────────────────────────
    if domain_stats:
        print(f"\n{BOLD}  🌐 PER-DOMAIN BREAKDOWN{RESET}")
        print(f"  {'─' * 68}")
        print(f"  {'Domain':<28} {'ATS':<12} {'Runs':>4} {'Rate':>6} {'Avg Dur':>8} {'Steps':>5}")
        print(f"  {'─' * 68}")

        for ds in domain_stats:
            rate = ds["success_rate"] or 0
            rate_color = GREEN if rate >= 70 else YELLOW if rate >= 40 else RED
            dom = (ds["website_domain"] or "?")[:27]
            ats = (ds["ats_platform"] or "-")[:11]
            print(
                f"  {dom:<28} {ats:<12} {ds['total_runs']:>4} "
                f"{rate_color}{rate:>5.0f}%{RESET} "
                f"{ds['avg_duration']:>7.0f}s {ds['avg_steps']:>5.0f}"
            )

    # ── Trend Over Time ───────────────────────────────────────────────────
    if trend and len(trend) > 1:
        print(f"\n{BOLD}  📈 TREND (batches of 5 runs){RESET}")
        print(f"  {'─' * 68}")
        print(f"  {'Batch':>5} {'Period':<25} {'Rate':>6} {'Chart':<22} {'Dur':>7} {'Mem':>4}")
        print(f"  {'─' * 68}")

        rates = [t["success_rate"] for t in trend]
        for t in trend:
            rate = t["success_rate"]
            rate_color = GREEN if rate >= 70 else YELLOW if rate >= 40 else RED
            print(
                f"  {t['batch']:>5} {t['period']:<25} "
                f"{rate_color}{rate:>5.0f}%{RESET} "
                f"{bar(rate, width=12):>22} "
                f"{t['avg_duration']:>6.0f}s "
                f"{t['avg_memories']:>3.0f}🧠"
            )

        print(f"\n  Sparkline: {spark(rates)}")

    # ── Recent Runs ───────────────────────────────────────────────────────
    recent = metrics.get_all_runs(limit=10)
    if recent:
        print(f"\n{BOLD}  🕐 RECENT RUNS (last 10){RESET}")
        print(f"  {'─' * 68}")
        for r in recent:
            status = f"{GREEN}✅{RESET}" if r["success"] else f"{RED}❌{RESET}"
            dom = (r["website_domain"] or "?")[:20]
            title = (r["job_title"] or "?")[:25]
            dur = r["duration_seconds"]
            steps = r["step_count"] or 0
            mems = r["memories_injected"]
            mem_icon = f"🧠{mems}" if mems > 0 else "  -"
            print(
                f"  {status} {dom:<20} {title:<25} "
                f"{dur:>6.0f}s {steps:>3}steps {mem_icon}"
            )

    print(f"\n{BOLD}{'═' * 70}{RESET}\n")


def print_json_dashboard(metrics: MetricsStore, mem_store: MemoryStore):
    """Output dashboard data as JSON."""
    data = {
        "overall": metrics.get_overall_stats(),
        "memory_impact": metrics.get_memory_impact(),
        "domain_stats": metrics.get_domain_stats(),
        "trend": metrics.get_trend(),
        "memory_store": mem_store.get_stats(),
        "recent_runs": metrics.get_all_runs(limit=20),
    }
    print(json.dumps(data, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Agent Performance Dashboard")
    parser.add_argument("--backfill", action="store_true", help="Backfill metrics from historical logs")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    metrics = MetricsStore()
    mem_store = MemoryStore()

    if args.backfill:
        backfill_metrics_from_logs(metrics, mem_store)

    if args.json:
        print_json_dashboard(metrics, mem_store)
    else:
        print_dashboard(metrics, mem_store)


if __name__ == "__main__":
    main()
