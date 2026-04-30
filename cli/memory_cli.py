#!/usr/bin/env python3
"""
CLI utility to inspect, manage, and maintain the agent memory store.

Usage:
  uv run python memory_cli.py stats                          # Overall stats
  uv run python memory_cli.py domains                        # List all domains with counts
  uv run python memory_cli.py show linkedin.com              # Show memories for a domain
  uv run python memory_cli.py show linkedin.com --category navigation
  uv run python memory_cli.py search "Easy Apply"            # Search memory content
  uv run python memory_cli.py decay                          # Decay old memories' confidence
  uv run python memory_cli.py cleanup                        # Remove low-confidence memories
  uv run python memory_cli.py export                         # Export all memories to JSON
  uv run python memory_cli.py import memories_backup.json    # Import memories from JSON
  uv run python memory_cli.py delete <id>                    # Delete a specific memory
  uv run python memory_cli.py reset                          # Reset entire memory store
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.memory import MemoryStore, CATEGORIES


def cmd_stats(store: MemoryStore, args):
    """Show overall memory statistics."""
    stats = store.get_stats()
    print(f"🧠 Agent Memory Store")
    print(f"{'='*50}")
    print(f"Total memories:  {stats['total_memories']}")
    print(f"Unique domains:  {stats['unique_domains']}")
    if stats['by_category']:
        print(f"\nBy category:")
        for cat, count in sorted(stats['by_category'].items(), key=lambda x: -x[1]):
            label = CATEGORIES.get(cat, cat)
            print(f"  {cat:<25} {count:>4}  — {label}")


def cmd_domains(store: MemoryStore, args):
    """List all domains with memory counts."""
    domains = store.get_all_domains()
    if not domains:
        print("No memories stored yet.")
        return

    print(f"{'Domain':<35} {'ATS':<15} {'Count':>5} {'Avg Conf':>8} {'✅':>4} {'❌':>4}")
    print(f"{'-'*75}")
    for d in domains:
        print(
            f"{d['website_domain']:<35} "
            f"{d['ats_platform'] or '-':<15} "
            f"{d['count']:>5} "
            f"{d['avg_confidence']:>8.2f} "
            f"{d['success_count']:>4} "
            f"{d['failure_count']:>4}"
        )
    print(f"\n{len(domains)} domains total")


def cmd_show(store: MemoryStore, args):
    """Show memories for a specific domain."""
    memories = store.search(
        website_domain=args.domain,
        category=args.category if hasattr(args, 'category') and args.category else None,
        success_only=not args.all,
        limit=args.limit,
    )

    if not memories:
        print(f"No memories for '{args.domain}'")
        if not args.all:
            print("  (try --all to include failure memories)")
        return

    print(f"🧠 Memories for {args.domain} ({len(memories)} results)")
    print(f"{'='*70}")

    current_cat = None
    for m in sorted(memories, key=lambda x: x['category']):
        if m['category'] != current_cat:
            current_cat = m['category']
            label = CATEGORIES.get(current_cat, current_cat)
            print(f"\n  [{label}]")

        status = "✅" if m['success'] else "❌"
        conf = f"{m['confidence']:.2f}"
        print(f"  {status} [{conf}] (id:{m['id']}) {m['content']}")


def cmd_search(store: MemoryStore, args):
    """Search memory content across all domains."""
    conn = store._get_conn()
    query = f"%{args.query}%"
    rows = conn.execute(
        "SELECT * FROM memories WHERE content LIKE ? ORDER BY confidence DESC LIMIT ?",
        (query, args.limit),
    ).fetchall()

    if not rows:
        print(f"No memories matching '{args.query}'")
        return

    print(f"🔍 Search results for '{args.query}' ({len(rows)} matches)")
    print(f"{'='*70}")
    for row in rows:
        m = dict(row)
        status = "✅" if m['success'] else "❌"
        print(f"  {status} [{m['confidence']:.2f}] {m['website_domain']} ({m['category']})")
        print(f"     {m['content']}")
        print()


def cmd_decay(store: MemoryStore, args):
    """Apply confidence decay to old memories."""
    affected = store.decay_confidence(days_old=args.days, decay_factor=args.factor)
    print(f"Decayed confidence for {affected} memories older than {args.days} days (factor: {args.factor})")


def cmd_consolidate(store: MemoryStore, args):
    """Consolidate company-specific ATS subdomains into their shared platform domain."""
    before = store.get_stats()
    print(f"Before: {before['total_memories']} memories across {before['unique_domains']} domains\n")

    migrations = store.consolidate_domains()

    if not migrations:
        print("✅ All domains are already normalized — nothing to consolidate.")
        return

    print("Migrations applied:")
    for label, count in sorted(migrations.items()):
        if label == "_duplicates_removed":
            print(f"  🗑️  Removed {count} duplicate memories after merge")
        else:
            print(f"  {label}: {count} memories")

    after = store.get_stats()
    print(f"\nAfter: {after['total_memories']} memories across {after['unique_domains']} domains")
    print(f"Reduced domains by {before['unique_domains'] - after['unique_domains']}")


def cmd_cleanup(store: MemoryStore, args):
    """Remove low-confidence memories."""
    removed = store.delete_low_confidence(threshold=args.threshold)
    print(f"Removed {removed} memories below confidence threshold {args.threshold}")


def cmd_export(store: MemoryStore, args):
    """Export all memories to JSON."""
    memories = store.export_all()
    output = args.output or "memory_export.json"

    # Convert to JSON-serializable format
    with open(output, "w") as f:
        json.dump(memories, f, indent=2, default=str)

    print(f"Exported {len(memories)} memories to {output}")


def cmd_import(store: MemoryStore, args):
    """Import memories from JSON file."""
    try:
        with open(args.file) as f:
            memories = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {args.file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        sys.exit(1)

    count = store.import_memories(memories)
    print(f"Imported {count} new memories from {args.file} ({len(memories)} total in file)")


def cmd_delete(store: MemoryStore, args):
    """Delete a specific memory by ID."""
    conn = store._get_conn()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (args.id,)).fetchone()
    if not row:
        print(f"Memory id={args.id} not found")
        sys.exit(1)

    m = dict(row)
    print(f"Deleting: [{m['website_domain']}] [{m['category']}] {m['content'][:80]}")

    if not args.yes:
        confirm = input("Confirm? [y/N] ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return

    conn.execute("DELETE FROM memories WHERE id = ?", (args.id,))
    conn.commit()
    print("Deleted.")


def cmd_reset(store: MemoryStore, args):
    """Reset the entire memory store."""
    if not args.yes:
        stats = store.get_stats()
        print(f"⚠️  This will delete ALL {stats['total_memories']} memories!")
        confirm = input("Type 'RESET' to confirm: ").strip()
        if confirm != "RESET":
            print("Cancelled.")
            return

    conn = store._get_conn()
    conn.execute("DELETE FROM memories")
    conn.commit()
    print("🗑️  All memories deleted.")


def main():
    parser = argparse.ArgumentParser(
        description="Agent Memory CLI — inspect, manage, and maintain the memory store",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # stats
    sub.add_parser("stats", help="Show overall memory statistics")

    # domains
    sub.add_parser("domains", help="List all domains with memory counts")

    # show
    p_show = sub.add_parser("show", help="Show memories for a specific domain")
    p_show.add_argument("domain", help="Website domain (e.g. linkedin.com)")
    p_show.add_argument("--category", "-c", choices=list(CATEGORIES.keys()), help="Filter by category")
    p_show.add_argument("--all", "-a", action="store_true", help="Include failure memories")
    p_show.add_argument("--limit", "-l", type=int, default=50, help="Max results")

    # search
    p_search = sub.add_parser("search", help="Search memory content")
    p_search.add_argument("query", help="Search text")
    p_search.add_argument("--limit", "-l", type=int, default=20, help="Max results")

    # decay
    p_decay = sub.add_parser("decay", help="Apply confidence decay to old memories")
    p_decay.add_argument("--days", type=int, default=30, help="Age threshold in days")
    p_decay.add_argument("--factor", type=float, default=0.95, help="Decay multiplier")

    # consolidate
    sub.add_parser("consolidate", help="Consolidate ATS subdomains (e.g. goodyear.wd1.myworkdayjobs.com → myworkdayjobs.com)")

    # cleanup
    p_cleanup = sub.add_parser("cleanup", help="Remove low-confidence memories")
    p_cleanup.add_argument("--threshold", type=float, default=0.3, help="Confidence threshold")

    # export
    p_export = sub.add_parser("export", help="Export all memories to JSON")
    p_export.add_argument("--output", "-o", help="Output file (default: memory_export.json)")

    # import
    p_import = sub.add_parser("import", help="Import memories from JSON")
    p_import.add_argument("file", help="JSON file to import")

    # delete
    p_delete = sub.add_parser("delete", help="Delete a specific memory by ID")
    p_delete.add_argument("id", type=int, help="Memory ID to delete")
    p_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    # reset
    p_reset = sub.add_parser("reset", help="Reset entire memory store")
    p_reset.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    store = MemoryStore()
    handlers = {
        "stats": cmd_stats,
        "domains": cmd_domains,
        "show": cmd_show,
        "search": cmd_search,
        "decay": cmd_decay,
        "consolidate": cmd_consolidate,
        "cleanup": cmd_cleanup,
        "export": cmd_export,
        "import": cmd_import,
        "delete": cmd_delete,
        "reset": cmd_reset,
    }
    handlers[args.command](store, args)


if __name__ == "__main__":
    main()
