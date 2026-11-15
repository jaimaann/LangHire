"""YAML-based plugin registry for job source plugins.

Loads built-in plugins from backend/sources/plugins/ and community plugins
from the user data directory (~/.langhire/plugins/).
"""

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

try:
    from core.config import get_data_dir
except ImportError:
    from backend.core.config import get_data_dir


REQUIRED_FIELDS = {"name", "display_name", "version", "author", "countries", "website", "collection_prompt", "apply_prompt"}


@dataclass
class AuthCookie:
    name: str
    domain: str


@dataclass
class DomainPattern:
    pattern: str
    normalize_to: str


@dataclass
class PluginFilter:
    key: str
    label: str
    type: str
    options: list[dict] = field(default_factory=list)
    url_param: str = ""
    default: str = ""


@dataclass
class PluginConfig:
    name: str
    display_name: str
    version: str
    author: str
    description: str
    countries: list[str]
    website: str
    requires_login: bool
    login_url: str
    search_url: str
    collection_prompt: str
    apply_prompt: str
    auth_cookies: list[AuthCookie] = field(default_factory=list)
    domain_patterns: list[DomainPattern] = field(default_factory=list)
    filters: list[PluginFilter] = field(default_factory=list)
    is_builtin: bool = False
    enabled: bool = True
    file_path: str = ""
    sha256: str = ""
    tampered: bool = False  # community file changed since the user approved it

    def render_collection_prompt(self, titles: list[str], locations: list[str], max_jobs: int, filters: dict | None = None) -> str:
        title = titles[0] if titles else ""
        location = locations[0] if locations else ""
        search_url = build_search_url(self.search_url, title, location, titles, locations, max_jobs)
        # Append filter URL params
        filter_params = []
        if filters:
            for f in self.filters:
                value = filters.get(f.key, "")
                if value and f.url_param:
                    filter_params.append(f"{f.url_param}={value}")
        else:
            for f in self.filters:
                if f.default and f.url_param:
                    filter_params.append(f"{f.url_param}={f.default}")
        if filter_params:
            sep = "&" if "?" in search_url else "?"
            search_url += sep + "&".join(filter_params)

        return self.collection_prompt.format(
            search_url=search_url,
            title=title, titles=", ".join(titles),
            location=location, locations=", ".join(locations),
            max_jobs=max_jobs,
        )

    def render_apply_prompt(
        self,
        job: dict,
        profile: dict,
        qa_bank: dict,
        resume_path: str = "",
        cover_letter: str = "",
        memories: str = "",
    ) -> str:
        profile_str = _format_profile(profile)
        qa_str = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa_bank.items() if a) if qa_bank else ""
        return self.apply_prompt.format(
            job_url=job.get("url", ""),
            job_title=job.get("title", ""),
            company=job.get("company", ""),
            profile=profile_str,
            resume_path=resume_path,
            qa_bank=qa_str,
            cover_letter=cover_letter,
            memories=memories,
        )


def _slug(text: str) -> str:
    """'Data Analyst' -> 'data-analyst'; 'Austin, TX' -> 'austin-tx' (path-style job boards)."""
    return re.sub(r"[^\w]+", "-", text.strip().lower(), flags=re.UNICODE).strip("-")


def build_search_url(template: str, title: str, location: str, titles: list[str], locations: list[str],
                     max_jobs: int) -> str:
    """Fill a plugin's search_url with properly encoded values.

    Placeholders in the query string are percent-encoded; placeholders in the
    path (Reed, Naukri, SEEK, StepStone use /data-analyst-jobs-in-london) are
    slugified. Raw values used to be inserted as-is, so 'Data Analyst' and
    'Austin, TX' produced URLs the boards mis-parsed.
    """
    from urllib.parse import quote_plus
    path, sep, query = template.partition("?")

    def fill(part: str, enc) -> str:
        return part.format(title=enc(title), titles=enc(", ".join(titles)), location=enc(location),
                           locations=enc(", ".join(locations)), max_jobs=max_jobs)

    url = fill(path, _slug)
    return url + (sep + fill(query, quote_plus) if sep else "")


def _format_profile(profile: dict) -> str:
    parts = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("email"):
        parts.append(f"Email: {profile['email']}")
    if profile.get("phone"):
        parts.append(f"Phone: {profile.get('phone_country_code', '')}{profile['phone']}")
    addr = profile.get("address", {})
    if addr.get("city"):
        parts.append(f"Location: {addr['city']}, {addr.get('state', '')} {addr.get('zip', '')} {addr.get('country', '')}")
    if profile.get("work_authorization"):
        parts.append(f"Work Authorization: {profile['work_authorization']}")
    if profile.get("notice_period"):
        parts.append(f"Notice Period: {profile['notice_period']}")
    if profile.get("nationality"):
        parts.append(f"Nationality: {profile['nationality']}")
    if profile.get("years_of_experience"):
        parts.append(f"Experience: {profile['years_of_experience']} years")
    edu = profile.get("education", {})
    if edu.get("degree"):
        parts.append(f"Education: {edu['degree']} from {edu.get('school', '')} ({edu.get('graduation', '')})")
    if profile.get("skills"):
        parts.append(f"Skills: {', '.join(profile['skills'])}")
    sal = profile.get("salary_expectation", {})
    if sal.get("min"):
        period = sal.get("period", "annual")
        parts.append(f"Salary: {sal['currency']} {sal['min']:,}-{sal['max']:,} ({period})")
    return "\n".join(parts)


def _parse_plugin_yaml(data: dict, file_path: str, is_builtin: bool) -> Optional[PluginConfig]:
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Plugin missing required fields: {missing}")

    auth_cookies = []
    for c in data.get("auth_cookies", []):
        if isinstance(c, dict) and "name" in c and "domain" in c:
            auth_cookies.append(AuthCookie(name=c["name"], domain=c["domain"]))

    domain_patterns = []
    for p in data.get("domain_patterns", []):
        if isinstance(p, dict) and "pattern" in p and "normalize_to" in p:
            domain_patterns.append(DomainPattern(pattern=p["pattern"], normalize_to=p["normalize_to"]))

    filters = []
    for f in data.get("filters", []):
        if isinstance(f, dict) and "key" in f and "label" in f:
            filters.append(PluginFilter(
                key=f["key"],
                label=f["label"],
                type=f.get("type", "select"),
                options=f.get("options", []),
                url_param=f.get("url_param", ""),
                default=f.get("default", ""),
            ))

    return PluginConfig(
        name=data["name"],
        display_name=data["display_name"],
        version=data["version"],
        author=data["author"],
        description=data.get("description", ""),
        countries=data["countries"],
        website=data["website"],
        requires_login=data.get("requires_login", False),
        login_url=data.get("login_url", ""),
        search_url=data.get("search_url", ""),
        collection_prompt=data["collection_prompt"],
        apply_prompt=data["apply_prompt"],
        auth_cookies=auth_cookies,
        domain_patterns=domain_patterns,
        filters=filters,
        is_builtin=is_builtin,
        enabled=True,
        file_path=file_path,
    )


_URL = re.compile(r"https?://([\w.-]+)", re.IGNORECASE)


def review_warnings(plugin: "PluginConfig") -> list[str]:
    """Things a user should look at before trusting a community plugin's prompts."""
    text = f"{plugin.collection_prompt}\n{plugin.apply_prompt}"
    low = text.lower()
    site = (plugin.website.split("//")[-1].split("/")[0]).lower().removeprefix("www.")
    warnings = []
    other_hosts = sorted({h.lower() for h in _URL.findall(text)
                          if site and not h.lower().removeprefix("www.").endswith(site)})
    if other_hosts:
        warnings.append("Sends the agent to other sites: " + ", ".join(other_hosts[:8]))
    for needle, why in (("mail.google", "Reads your email"), ("password", "Mentions passwords"),
                        ("secret", "Mentions secrets"), ("ignore previous", "Tries to override instructions"),
                        ("api key", "Mentions API keys")):
        if needle in low:
            warnings.append(why)
    return warnings


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, PluginConfig] = {}
        self._approved: dict[str, str] = {}
        self._load_all()

    def _get_builtin_dir(self) -> Path:
        import sys
        if getattr(sys, 'frozen', False):
            # PyInstaller bundles data into sys._MEIPASS
            base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
            return base / "sources" / "plugins"
        return Path(__file__).parent / "plugins"

    def _get_community_dir(self) -> Path:
        d = get_data_dir() / "plugins"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_yaml_file(self, path: Path, is_builtin: bool) -> Optional[PluginConfig]:
        try:
            raw = path.read_bytes()
            data = yaml.safe_load(raw.decode("utf-8"))
            if not isinstance(data, dict):
                return None
            plugin = _parse_plugin_yaml(data, str(path), is_builtin)
            if plugin:
                plugin.sha256 = hashlib.sha256(raw).hexdigest()
            return plugin
        except Exception as e:
            import logging
            logging.getLogger("plugins").warning(f"Failed to load plugin {path.name}: {e}")
            return None

    def _load_all(self):
        self._plugins.clear()
        # Load built-in plugins
        builtin_dir = self._get_builtin_dir()
        if builtin_dir.exists():
            for f in sorted(builtin_dir.glob("*.yaml")):
                plugin = self._load_yaml_file(f, is_builtin=True)
                if plugin:
                    self._plugins[plugin.name] = plugin

        # Load community plugins
        community_dir = self._get_community_dir()
        if community_dir.exists():
            for f in sorted(community_dir.glob("*.yaml")):
                plugin = self._load_yaml_file(f, is_builtin=False)
                if plugin and plugin.name not in self._plugins:
                    self._plugins[plugin.name] = plugin

        # Load enabled/disabled state
        self._load_state()

    def _get_state_path(self) -> Path:
        return get_data_dir() / "plugin_state.json"

    def _load_state(self):
        import json
        state_path = self._get_state_path()
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                hashes = state.pop("_approved_sha256", {}) if isinstance(state, dict) else {}
                self._approved = dict(hashes)
                for name, enabled in state.items():
                    if name in self._plugins and isinstance(enabled, bool):
                        self._plugins[name].enabled = enabled
            except Exception:
                pass
        # A community plugin whose file changed after approval stays disabled
        for p in self._plugins.values():
            if not p.is_builtin:
                pinned = self._approved.get(p.name)
                if pinned and pinned != p.sha256:
                    p.tampered = True
                    p.enabled = False

    def _save_state(self):
        import json
        state: dict = {name: p.enabled for name, p in self._plugins.items()}
        state["_approved_sha256"] = dict(self._approved)
        state_path = self._get_state_path()
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_all(self) -> list[PluginConfig]:
        return list(self._plugins.values())

    def get_enabled(self) -> list[PluginConfig]:
        return [p for p in self._plugins.values() if p.enabled]

    def get_by_name(self, name: str) -> Optional[PluginConfig]:
        return self._plugins.get(name)

    def get_for_country(self, country_code: str) -> list[PluginConfig]:
        return [
            p for p in self._plugins.values()
            if p.enabled and (country_code in p.countries or "ALL" in p.countries)
        ]

    def set_enabled(self, name: str, enabled: bool) -> bool:
        if name not in self._plugins:
            return False
        self._plugins[name].enabled = enabled
        self._save_state()
        return True

    def preview_plugin(self, source_path: str) -> dict:
        """Parse a plugin file without installing it, for the user to review."""
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Plugin file not found: {source_path}")
        if source.suffix not in (".yaml", ".yml"):
            raise ValueError("Plugin must be a .yaml or .yml file")
        plugin = self._load_yaml_file(source, is_builtin=False)
        if not plugin:
            raise ValueError("Invalid plugin file: failed to parse")
        return {
            "name": plugin.name, "display_name": plugin.display_name, "version": plugin.version,
            "author": plugin.author, "website": plugin.website, "requires_login": plugin.requires_login,
            "sha256": plugin.sha256, "collection_prompt": plugin.collection_prompt,
            "apply_prompt": plugin.apply_prompt, "warnings": review_warnings(plugin),
        }

    def import_plugin(self, source_path: str, approved_sha256: str | None = None) -> PluginConfig:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Plugin file not found: {source_path}")
        if source.suffix not in (".yaml", ".yml"):
            raise ValueError("Plugin must be a .yaml or .yml file")

        plugin = self._load_yaml_file(source, is_builtin=False)
        if not plugin:
            raise ValueError("Invalid plugin file: failed to parse")
        if plugin.name in self._plugins and self._plugins[plugin.name].is_builtin:
            raise ValueError(f"Cannot override built-in plugin: {plugin.name}")
        if approved_sha256 is not None and approved_sha256 != plugin.sha256:
            raise ValueError("The plugin file changed after you reviewed it; review it again")
        self._approved[plugin.name] = plugin.sha256

        dest = self._get_community_dir() / source.name
        shutil.copy2(source, dest)
        plugin.file_path = str(dest)
        self._plugins[plugin.name] = plugin
        self._save_state()
        return plugin

    def remove_plugin(self, name: str) -> bool:
        if name not in self._plugins:
            return False
        plugin = self._plugins[name]
        if plugin.is_builtin:
            raise ValueError("Cannot remove built-in plugins (disable instead)")
        file_path = Path(plugin.file_path)
        if file_path.exists():
            file_path.unlink()
        del self._plugins[name]
        self._approved.pop(name, None)
        self._save_state()
        return True

    def reload(self):
        self._load_all()
