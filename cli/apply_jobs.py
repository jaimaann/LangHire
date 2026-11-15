"""
Apply to collected jobs from the command line (same engine as the app).

Usage:
  uv run python cli/apply_jobs.py                       # all pending jobs, 1 worker
  uv run python cli/apply_jobs.py --workers 2 --limit 10
  uv run python cli/apply_jobs.py --mode easy           # only the boards' quick-apply jobs
  uv run python cli/apply_jobs.py --url https://...     # one job
"""
import argparse

from _engine_cli import run

from engine.apply import run_apply


def main():
    p = argparse.ArgumentParser(description="Apply to collected jobs")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--limit", type=int)
    p.add_argument("--mode", choices=["easy", "external", "all"], default="all")
    p.add_argument("--url", help="Apply to one job URL")
    a = p.parse_args()
    stats = run("apply", lambda ctx: run_apply(ctx, mode=a.mode, workers=a.workers, limit=a.limit, job_url=a.url),
                vars(a))
    print(f"Results: {stats}")


if __name__ == "__main__":
    main()
