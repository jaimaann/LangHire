"""
SQLite-based agent memory store for per-website learning.

Stores procedural memories about website navigation, form interactions,
and application strategies. Memories are keyed by website domain and
categorized for efficient retrieval.

Architecture note: This is a lightweight, zero-dependency implementation
using SQLite. Could be swapped for Mem0 or a vector DB backend by
reimplementing the MemoryStore class with the same interface.
"""

import hashlib
import re as _re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


# ── Memory categories ────────────────────────────────────────────────────────
CATEGORIES = {
    "navigation":          "How to navigate to/through the application form",
    "form_strategy":       "Overall strategy for completing applications on this site",
    "element_interaction": "Specific UI element interactions (checkboxes, dropdowns, modals, etc.)",
    "failure_recovery":    "How to handle errors, edge cases, and blockers",
    "site_structure":      "General structure of the application flow / ATS layout",
    "qa_pattern":          "Patterns in questions asked and input types used",
}

# ── Known ATS platform domain patterns ───────────────────────────────────────
ATS_DOMAINS: dict[str, str] = {
    "linkedin.com":          "linkedin",
    "greenhouse.io":         "greenhouse",
    "boards.greenhouse.io":  "greenhouse",
    "lever.co":              "lever",
    "jobs.lever.co":         "lever",
    "myworkdayjobs.com":     "workday",
    "workday.com":           "workday",
    "icims.com":             "icims",
    "smartrecruiters.com":   "smartrecruiters",
    "jobvite.com":           "jobvite",
    "breezy.hr":             "breezy",
    "ashbyhq.com":           "ashby",
    "bamboohr.com":          "bamboohr",
    "jazz.co":               "jazzhr",
    "applytojob.com":        "jazzhr",
    "ultipro.com":           "ultipro",
    "taleo.net":             "taleo",
    "successfactors.com":    "successfactors",
    "paylocity.com":         "paylocity",
    "adp.com":               "adp",
    "paycomonline.net":      "paycom",
    "indeed.com":            "indeed",
    "ziprecruiter.com":      "ziprecruiter",
}

# ── Domain normalization rules ────────────────────────────────────────────────
# Maps company-specific subdomains to their shared ATS platform domain.
# e.g., goodyear.wd1.myworkdayjobs.com → myworkdayjobs.com
DOMAIN_NORMALIZATION: list[tuple[str, str]] = [
    # Workday: {company}.wd{N}.myworkdayjobs.com → myworkdayjobs.com
    (r"\.wd\d+\.myworkdayjobs\.com$", "myworkdayjobs.com"),
    (r"\.myworkdayjobs\.com$", "myworkdayjobs.com"),
    # Oracle Cloud HCM: {code}.fa.{region}.oraclecloud.com → oraclecloud.com
    (r"\.fa\.\w+\.oraclecloud\.com$", "oraclecloud.com"),
    (r"\.oraclecloud\.com$", "oraclecloud.com"),
    # SuccessFactors: {instance}.successfactors.com → successfactors.com
    (r"\w+\.successfactors\.com$", "successfactors.com"),
    # Greenhouse: job-boards.greenhouse.io, boards.greenhouse.io → greenhouse.io
    (r"[\w-]+\.greenhouse\.io$", "greenhouse.io"),
    # Lever: jobs.lever.co → lever.co
    (r"[\w-]+\.lever\.co$", "lever.co"),
    # ADP: myjobs.adp.com, workforcenow.adp.com, recruiting.adp.com → adp.com
    (r"[\w-]+\.adp\.com$", "adp.com"),
    # iCIMS: {company}.icims.com → icims.com
    (r"[\w-]+\.icims\.com$", "icims.com"),
    # SmartRecruiters: {company}.smartrecruiters.com → smartrecruiters.com
    (r"[\w-]+\.smartrecruiters\.com$", "smartrecruiters.com"),
    # BambooHR: {company}.bamboohr.com → bamboohr.com
    (r"[\w-]+\.bamboohr\.com$", "bamboohr.com"),
    # Ashby: jobs.ashbyhq.com → ashbyhq.com
    (r"[\w-]+\.ashbyhq\.com$", "ashbyhq.com"),
    # Jobvite: {company}.jobvite.com → jobvite.com
    (r"[\w-]+\.jobvite\.com$", "jobvite.com"),
    # Taleo: {company}.taleo.net → taleo.net
    (r"[\w-]+\.taleo\.net$", "taleo.net"),
    # Paylocity: {company}.paylocity.com → paylocity.com
    (r"[\w-]+\.paylocity\.com$", "paylocity.com"),
    # UltiPro: {company}.ultipro.com → ultipro.com
    (r"[\w-]+\.ultipro\.com$", "ultipro.com"),
]


import sys

try:
    from core.config import get_data_dir
except ImportError:
    from backend.core.config import get_data_dir


def _get_db_path() -> Path:
    if getattr(sys, 'frozen', False):
        return get_data_dir() / "memory_store.db"
    return Path(__file__).parent.parent.parent / "memory_store.db"

DB_PATH = _get_db_path()


class MemoryStore:
    """SQLite-backed memory store with per-domain retrieval and deduplication."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    # ── Connection management ─────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def close(self):
        """Close the thread-local connection if open."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

    def __del__(self):
        self.close()

    def _init_db(self):
        """Create tables, indexes, and run migrations if needed."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS memories (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                website_domain TEXT NOT NULL,
                ats_platform   TEXT,
                category       TEXT NOT NULL,
                content        TEXT NOT NULL,
                content_hash   TEXT UNIQUE,
                success        INTEGER DEFAULT 1,
                confidence     REAL    DEFAULT 0.8,
                job_url        TEXT,
                created_at     TEXT NOT NULL,
                updated_at     TEXT NOT NULL,
                access_count   INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_memories_domain
                ON memories(website_domain);
            CREATE INDEX IF NOT EXISTS idx_memories_category
                ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_memories_ats
                ON memories(ats_platform);
            CREATE INDEX IF NOT EXISTS idx_memories_hash
                ON memories(content_hash);
            CREATE INDEX IF NOT EXISTS idx_memories_confidence
                ON memories(confidence DESC);
        """)
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version = row[0] if row and row[0] else 0
        if current_version < 1:
            conn.execute("INSERT OR REPLACE INTO schema_version VALUES (1)")
        conn.commit()

    # ── Domain / ATS helpers ──────────────────────────────────────────────

    @staticmethod
    def normalize_domain(domain: str) -> str:
        """Normalize a domain by collapsing company-specific ATS subdomains.

        >>> MemoryStore.normalize_domain("goodyear.wd1.myworkdayjobs.com")
        'myworkdayjobs.com'
        >>> MemoryStore.normalize_domain("eiqg.fa.us2.oraclecloud.com")
        'oraclecloud.com'
        >>> MemoryStore.normalize_domain("career4.successfactors.com")
        'successfactors.com'
        >>> MemoryStore.normalize_domain("myjobs.adp.com")
        'adp.com'
        >>> MemoryStore.normalize_domain("linkedin.com")
        'linkedin.com'
        """
        for pattern, replacement in DOMAIN_NORMALIZATION:
            if _re.search(pattern, domain):
                return replacement
        return domain

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract and normalize the domain from a URL.

        >>> MemoryStore.extract_domain("https://www.linkedin.com/jobs/view/123")
        'linkedin.com'
        >>> MemoryStore.extract_domain("https://goodyear.wd1.myworkdayjobs.com/job/123")
        'myworkdayjobs.com'
        >>> MemoryStore.extract_domain("https://eiqg.fa.us2.oraclecloud.com/hcmUI/...")
        'oraclecloud.com'
        """
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            if host.startswith("www."):
                host = host[4:]
            return MemoryStore.normalize_domain(host.lower())
        except Exception:
            return ""

    @staticmethod
    def detect_ats_platform(domain: str) -> Optional[str]:
        """Detect the ATS platform from a domain string."""
        for pattern, ats in ATS_DOMAINS.items():
            if pattern in domain:
                return ats
        return None

    @staticmethod
    def _content_hash(content: str, domain: str, category: str) -> str:
        """Generate a short hash for deduplication."""
        normalized = f"{domain}|{category}|{content.lower().strip()}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    # ── Core CRUD ─────────────────────────────────────────────────────────

    def add(
        self,
        content: str,
        website_domain: str,
        category: str,
        success: bool = True,
        confidence: float = 0.8,
        job_url: str = "",
        ats_platform: str | None = None,
    ) -> bool:
        """Add a memory. Returns True if new, False if duplicate (confidence bumped)."""
        if not content.strip():
            return False

        if category not in CATEGORIES:
            category = "form_strategy"  # safe default

        if ats_platform is None:
            ats_platform = self.detect_ats_platform(website_domain)

        content_hash = self._content_hash(content, website_domain, category)
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()

        # Check for duplicate
        existing = conn.execute(
            "SELECT id, confidence, access_count FROM memories WHERE content_hash = ?",
            (content_hash,),
        ).fetchone()

        if existing:
            new_confidence = min(1.0, existing["confidence"] + 0.05)
            conn.execute(
                "UPDATE memories SET confidence = ?, access_count = access_count + 1, "
                "updated_at = ? WHERE id = ?",
                (new_confidence, now, existing["id"]),
            )
            conn.commit()
            return False  # duplicate — reinforced

        conn.execute(
            """INSERT INTO memories
               (website_domain, ats_platform, category, content, content_hash,
                success, confidence, job_url, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                website_domain, ats_platform, category, content.strip(),
                content_hash, int(success), confidence, job_url, now, now,
            ),
        )
        conn.commit()
        return True  # new memory

    def search(
        self,
        website_domain: str | None = None,
        ats_platform: str | None = None,
        category: str | None = None,
        success_only: bool = True,
        limit: int = 20,
    ) -> list[dict]:
        """Retrieve memories filtered by domain / platform / category.

        Results ordered by confidence DESC, access_count DESC.
        """
        conditions: list[str] = []
        params: list = []

        if website_domain:
            conditions.append("website_domain = ?")
            params.append(website_domain)

        if ats_platform:
            conditions.append("ats_platform = ?")
            params.append(ats_platform)

        if category:
            conditions.append("category = ?")
            params.append(category)

        if success_only:
            conditions.append("success = 1")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT * FROM memories {where} "
            f"ORDER BY confidence DESC, access_count DESC LIMIT ?",
            params + [limit],
        ).fetchall()

        ids = [int(row["id"]) for row in rows]
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE memories SET access_count = access_count + 1 "
                f"WHERE id IN ({placeholders})",
                ids,
            )
            conn.commit()

        return [dict(row) for row in rows]

    def get_domain_memories(self, job_url: str, limit: int = 20) -> list[dict]:
        """Get all relevant memories for a job URL (domain + ATS platform combined)."""
        domain = self.extract_domain(job_url)
        if not domain:
            return []

        # Domain-specific memories
        memories = self.search(website_domain=domain, limit=limit)

        # Also pull ATS-platform memories from other domains on same ATS
        ats = self.detect_ats_platform(domain)
        if ats:
            ats_memories = self.search(ats_platform=ats, limit=limit // 2)
            seen_ids = {m["id"] for m in memories}
            for m in ats_memories:
                if m["id"] not in seen_ids:
                    memories.append(m)
                    seen_ids.add(m["id"])

        return memories[:limit]

    # ── Reporting ─────────────────────────────────────────────────────────

    def get_all_domains(self) -> list[dict]:
        """Summary of memories grouped by domain."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT website_domain, ats_platform,
                   COUNT(*)                                         AS count,
                   ROUND(AVG(confidence), 2)                        AS avg_confidence,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END)    AS success_count,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END)    AS failure_count
            FROM memories
            GROUP BY website_domain
            ORDER BY count DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Overall memory statistics."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        domains = conn.execute(
            "SELECT COUNT(DISTINCT website_domain) FROM memories"
        ).fetchone()[0]
        by_category = dict(
            conn.execute(
                "SELECT category, COUNT(*) FROM memories GROUP BY category"
            ).fetchall()
        )
        return {
            "total_memories": total,
            "unique_domains": domains,
            "by_category": by_category,
        }

    # ── Maintenance ───────────────────────────────────────────────────────

    def decay_confidence(self, days_old: int = 30, decay_factor: float = 0.95):
        """Reduce confidence of stale memories (websites change their UI)."""
        conn = self._get_conn()
        affected = conn.execute(
            """UPDATE memories
               SET confidence = MAX(0.3, confidence * ?)
               WHERE julianday('now') - julianday(updated_at) > ?""",
            (decay_factor, days_old),
        ).rowcount
        conn.commit()
        return affected

    def consolidate_domains(self) -> dict[str, int]:
        """Migrate memories from company-specific subdomains to their normalized ATS domain.

        e.g., goodyear.wd1.myworkdayjobs.com → myworkdayjobs.com

        Returns a dict mapping old_domain → count of migrated memories.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT website_domain FROM memories"
        ).fetchall()

        migrations: dict[str, int] = {}
        now = datetime.now(timezone.utc).isoformat()

        for row in rows:
            old_domain = row["website_domain"]
            new_domain = self.normalize_domain(old_domain)

            if new_domain != old_domain:
                # Update domain and re-detect ATS platform
                new_ats = self.detect_ats_platform(new_domain)
                count = conn.execute(
                    "UPDATE memories SET website_domain = ?, ats_platform = ?, "
                    "updated_at = ? WHERE website_domain = ?",
                    (new_domain, new_ats, now, old_domain),
                ).rowcount
                if count > 0:
                    migrations[f"{old_domain} → {new_domain}"] = count

        if migrations:
            conn.commit()

            # Now deduplicate — same content on same domain may now be duplicates
            # Find duplicate content_hashes after migration and keep highest confidence
            dupes = conn.execute("""
                SELECT content, website_domain, category, COUNT(*) as cnt
                FROM memories
                GROUP BY LOWER(TRIM(content)), website_domain, category
                HAVING cnt > 1
            """).fetchall()

            dedup_count = 0
            for dupe in dupes:
                # Keep the one with highest confidence, delete the rest
                rows = conn.execute(
                    "SELECT id, confidence FROM memories "
                    "WHERE website_domain = ? AND category = ? AND LOWER(TRIM(content)) = LOWER(TRIM(?)) "
                    "ORDER BY confidence DESC, access_count DESC",
                    (dupe["website_domain"], dupe["category"], dupe["content"]),
                ).fetchall()
                if len(rows) > 1:
                    ids_to_delete = [int(r["id"]) for r in rows[1:]]
                    if ids_to_delete:
                        placeholders = ",".join("?" * len(ids_to_delete))
                        conn.execute(
                            f"DELETE FROM memories WHERE id IN ({placeholders})",
                            ids_to_delete,
                        )
                        dedup_count += len(ids_to_delete)

            if dedup_count > 0:
                conn.commit()
                migrations["_duplicates_removed"] = dedup_count

        return migrations

    def delete_low_confidence(self, threshold: float = 0.3) -> int:
        """Remove memories below confidence threshold."""
        conn = self._get_conn()
        affected = conn.execute(
            "DELETE FROM memories WHERE confidence < ?", (threshold,)
        ).rowcount
        conn.commit()
        return affected

    def export_all(self) -> list[dict]:
        """Export all memories as a list of dicts (for JSON backup)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY website_domain, category"
        ).fetchall()
        return [dict(r) for r in rows]

    def import_memories(self, memories: list[dict]) -> int:
        """Import memories from a list of dicts. Returns count of new memories added."""
        count = 0
        for m in memories:
            is_new = self.add(
                content=m.get("content", ""),
                website_domain=m.get("website_domain", ""),
                category=m.get("category", "form_strategy"),
                success=bool(m.get("success", True)),
                confidence=m.get("confidence", 0.8),
                job_url=m.get("job_url", ""),
                ats_platform=m.get("ats_platform"),
            )
            if is_new:
                count += 1
        return count

    # ── Prompt formatting ─────────────────────────────────────────────────

    def format_for_prompt(self, memories: list[dict]) -> str:
        """Format memories into a string suitable for injection into the agent's system prompt."""
        if not memories:
            return ""

        # Group by category for readability
        by_category: dict[str, list[str]] = {}
        for m in memories:
            cat = m.get("category", "general")
            label = CATEGORIES.get(cat, cat.replace("_", " ").title())
            by_category.setdefault(label, []).append(m["content"])

        parts = [
            "WEBSITE-SPECIFIC LEARNINGS (from previous successful applications on this site):"
        ]
        for cat_label, items in by_category.items():
            parts.append(f"\n  [{cat_label}]")
            for item in items:
                parts.append(f"  • {item}")

        return "\n".join(parts)
