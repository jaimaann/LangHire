#!/usr/bin/env python3
"""
Demo script: Seeds realistic sample memories and displays them raw.

Usage:
  uv run python memory_demo.py              # Seed + display all raw memories
  uv run python memory_demo.py --raw-only   # Just dump current raw DB contents
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.memory import MemoryStore


SAMPLE_MEMORIES = [
    # ── LinkedIn ──────────────────────────────────────────────────────────
    {
        "content": "LinkedIn Easy Apply opens as a modal overlay dialog on top of the job page — do NOT navigate away or click the browser back button.",
        "website_domain": "linkedin.com",
        "category": "navigation",
        "success": True,
        "confidence": 0.9,
        "job_url": "https://www.linkedin.com/jobs/view/4012345678/",
    },
    {
        "content": "The Easy Apply form typically has 3-5 steps: Contact Info → Resume Upload → Additional Questions → Review → Submit application.",
        "website_domain": "linkedin.com",
        "category": "site_structure",
        "success": True,
        "confidence": 0.95,
        "job_url": "https://www.linkedin.com/jobs/view/4012345678/",
    },
    {
        "content": "After clicking 'Submit application', wait for the green success toast notification that says 'Your application was sent' before calling done.",
        "website_domain": "linkedin.com",
        "category": "form_strategy",
        "success": True,
        "confidence": 0.88,
        "job_url": "https://www.linkedin.com/jobs/view/4023456789/",
    },
    {
        "content": "The 'I agree to the terms' checkbox is sometimes inside a scrollable container within the modal — scroll down inside the modal to find it.",
        "website_domain": "linkedin.com",
        "category": "element_interaction",
        "success": True,
        "confidence": 0.85,
        "job_url": "https://www.linkedin.com/jobs/view/4023456789/",
    },
    {
        "content": "LinkedIn may show 'You've reached the Easy Apply limit' — when this happens, skip the job and mark as failed with error 'rate_limited'.",
        "website_domain": "linkedin.com",
        "category": "failure_recovery",
        "success": False,
        "confidence": 0.7,
        "job_url": "https://www.linkedin.com/jobs/view/4034567890/",
    },
    {
        "content": "The 'How many years of experience do you have with X?' questions use a text input, not a dropdown — type the number directly.",
        "website_domain": "linkedin.com",
        "category": "qa_pattern",
        "success": True,
        "confidence": 0.92,
        "job_url": "https://www.linkedin.com/jobs/view/4034567890/",
    },

    # ── Greenhouse ────────────────────────────────────────────────────────
    {
        "content": "Greenhouse application forms are a single long page with all fields visible — no step-by-step wizard navigation needed.",
        "website_domain": "boards.greenhouse.io",
        "category": "site_structure",
        "success": True,
        "confidence": 0.85,
        "job_url": "https://boards.greenhouse.io/acme/jobs/12345",
    },
    {
        "content": "The resume upload on Greenhouse uses a file picker button — click 'Attach' or 'Choose File' and select the resume PDF.",
        "website_domain": "boards.greenhouse.io",
        "category": "element_interaction",
        "success": True,
        "confidence": 0.82,
        "job_url": "https://boards.greenhouse.io/acme/jobs/12345",
    },
    {
        "content": "Greenhouse 'How did you hear about this job?' is always a dropdown with options like 'LinkedIn', 'Referral', 'Company Website'.",
        "website_domain": "boards.greenhouse.io",
        "category": "qa_pattern",
        "success": True,
        "confidence": 0.80,
        "job_url": "https://boards.greenhouse.io/acme/jobs/12345",
    },

    # ── Lever ─────────────────────────────────────────────────────────────
    {
        "content": "Lever application pages have the job description on the left and the application form on the right side of the page.",
        "website_domain": "jobs.lever.co",
        "category": "site_structure",
        "success": True,
        "confidence": 0.83,
        "job_url": "https://jobs.lever.co/company/abc-123",
    },
    {
        "content": "Lever forms always start with Name, Email, Phone, then Resume upload — fill in order from top to bottom.",
        "website_domain": "jobs.lever.co",
        "category": "form_strategy",
        "success": True,
        "confidence": 0.80,
        "job_url": "https://jobs.lever.co/company/abc-123",
    },

    # ── Workday ───────────────────────────────────────────────────────────
    {
        "content": "Workday requires creating an account before applying — use the candidate's email and password from sensitive_data.",
        "website_domain": "myworkdayjobs.com",
        "category": "navigation",
        "success": True,
        "confidence": 0.90,
        "job_url": "https://company.wd5.myworkdayjobs.com/external/job/12345",
    },
    {
        "content": "Workday's 'My Experience' page has an autofill option — click 'Upload Resume' first and it will pre-fill work history fields.",
        "website_domain": "myworkdayjobs.com",
        "category": "form_strategy",
        "success": True,
        "confidence": 0.78,
        "job_url": "https://company.wd5.myworkdayjobs.com/external/job/12345",
    },
    {
        "content": "Workday forms are multi-page: My Information → My Experience → Application Questions → Voluntary Disclosures → Review & Submit.",
        "website_domain": "myworkdayjobs.com",
        "category": "site_structure",
        "success": True,
        "confidence": 0.85,
        "job_url": "https://company.wd5.myworkdayjobs.com/external/job/12345",
    },
    {
        "content": "Workday session timeout after ~15 minutes of inactivity — if the page shows a timeout error, refresh and re-login.",
        "website_domain": "myworkdayjobs.com",
        "category": "failure_recovery",
        "success": False,
        "confidence": 0.65,
        "job_url": "https://company.wd5.myworkdayjobs.com/external/job/67890",
    },
]


def seed_memories(store: MemoryStore) -> int:
    """Seed the store with sample memories. Returns count of new memories added."""
    count = 0
    for m in SAMPLE_MEMORIES:
        is_new = store.add(
            content=m["content"],
            website_domain=m["website_domain"],
            category=m["category"],
            success=m["success"],
            confidence=m["confidence"],
            job_url=m.get("job_url", ""),
        )
        if is_new:
            count += 1
    return count


def dump_raw_memories(store: MemoryStore):
    """Dump ALL memories from the SQLite database as raw rows."""
    conn = store._get_conn()
    rows = conn.execute("SELECT * FROM memories ORDER BY website_domain, category, id").fetchall()

    if not rows:
        print("📭 Memory store is empty — no memories to display.\n")
        print("Run this script without --raw-only to seed sample memories first:")
        print("  python3 memory_demo.py")
        return

    print(f"🧠 RAW MEMORY DUMP — {len(rows)} memories in memory_store.db")
    print(f"{'='*100}\n")

    current_domain = None
    for row in rows:
        m = dict(row)

        # Domain header
        if m["website_domain"] != current_domain:
            current_domain = m["website_domain"]
            ats = m["ats_platform"] or "unknown"
            print(f"┌─── {current_domain} (ATS: {ats}) ───────────────────────────────")

        # Raw fields
        status = "✅ success" if m["success"] else "❌ failure"
        print(f"│")
        print(f"│  ID:          {m['id']}")
        print(f"│  Category:    {m['category']}")
        print(f"│  Content:     {m['content']}")
        print(f"│  Status:      {status}")
        print(f"│  Confidence:  {m['confidence']:.2f}")
        print(f"│  Hash:        {m['content_hash']}")
        print(f"│  Job URL:     {m['job_url'] or '—'}")
        print(f"│  Created:     {m['created_at']}")
        print(f"│  Updated:     {m['updated_at']}")
        print(f"│  Accessed:    {m['access_count']} times")

    print(f"│")
    print(f"└{'─'*99}")

    # Summary
    print(f"\n📊 Summary:")
    domains = set(dict(r)["website_domain"] for r in rows)
    categories = {}
    for r in rows:
        cat = dict(r)["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"  Domains:    {', '.join(sorted(domains))}")
    print(f"  Categories: {json.dumps(categories, indent=None)}")
    print(f"  Total:      {len(rows)} memories")


def dump_as_json(store: MemoryStore):
    """Dump all memories as pretty-printed JSON."""
    memories = store.export_all()
    if not memories:
        print("📭 No memories to export.")
        return
    print(json.dumps(memories, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Demo: seed and view raw agent memories")
    parser.add_argument("--raw-only", action="store_true", help="Only dump current DB contents (don't seed)")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of table")
    parser.add_argument("--reset", action="store_true", help="Clear all memories before seeding")
    args = parser.parse_args()

    store = MemoryStore()

    if args.reset:
        conn = store._get_conn()
        conn.execute("DELETE FROM memories")
        conn.commit()
        print("🗑️  Cleared all existing memories.\n")

    if not args.raw_only:
        count = seed_memories(store)
        if count > 0:
            print(f"🌱 Seeded {count} new sample memories.\n")
        else:
            print(f"ℹ️  All sample memories already exist (duplicates skipped).\n")

    if args.json:
        dump_as_json(store)
    else:
        dump_raw_memories(store)


if __name__ == "__main__":
    main()
