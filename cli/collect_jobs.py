"""
Collect job listings from a job source plugin (same engine as the app).

Usage:
  uv run python cli/collect_jobs.py                          # all target titles, LinkedIn
  uv run python cli/collect_jobs.py --source indeed --title "Data Analyst" --max-jobs 20
"""
import argparse

from _engine_cli import run

from engine.collect import run_collect


def main():
    p = argparse.ArgumentParser(description="Collect job listings")
    p.add_argument("--title", help="Collect for a single job title (default: all profile titles)")
    p.add_argument("--source", default="linkedin", help="Plugin name, e.g. linkedin, indeed, seek")
    p.add_argument("--max-jobs", type=int, default=0)
    a = p.parse_args()
    stats = run("collect", lambda ctx: run_collect(ctx, title=a.title, source=a.source, max_jobs=a.max_jobs,
                                                   filters=None), vars(a))
    print(f"Results: {stats}")


if __name__ == "__main__":
    main()
