"""Unit tests for the YAML-based job-source plugin registry.

Covers plugin discovery/loading of the bundled plugins, schema validation,
graceful handling of missing/malformed plugin files, the dataclass parsing
helpers, URL building + filter mapping in ``render_collection_prompt``,
``render_apply_prompt`` / ``_format_profile``, and the registry mutation
methods (enable/disable, import, remove, reload).

All file I/O goes through the ``data_dir`` fixture, which redirects HOME to a
throwaway tmp dir so the user's real community-plugin/state files are untouched.
No network access is performed.
"""
import json
import textwrap
from pathlib import Path

import pytest
import yaml

from sources.registry import (
    AuthCookie,
    DomainPattern,
    PluginConfig,
    PluginFilter,
    PluginRegistry,
    REQUIRED_FIELDS,
    _format_profile,
    _parse_plugin_yaml,
)

# Plugins bundled in backend/sources/plugins/*.yaml.
BUNDLED_PLUGINS = {
    "seek",
    "reed",
    "stepstone",
    "ziprecruiter",
    "indeed",
    "linkedin",
    "naukri",
}


# ── Helpers ────────────────────────────────────────────────────────────────

def _minimal_plugin_dict(**overrides) -> dict:
    """A dict satisfying REQUIRED_FIELDS, ready for _parse_plugin_yaml."""
    data = {
        "name": "acme",
        "display_name": "Acme Jobs",
        "version": "1.0.0",
        "author": "tester",
        "countries": ["US"],
        "website": "https://acme.example",
        "collection_prompt": "collect {search_url}",
        "apply_prompt": "apply {job_url}",
    }
    data.update(overrides)
    return data


@pytest.fixture
def registry(data_dir):
    """A PluginRegistry bound to an isolated tmp data dir."""
    return PluginRegistry()


# ── Bundled-plugin discovery ────────────────────────────────────────────────

class TestBundledDiscovery:
    """The registry must discover and load all shipped plugins."""

    def test_loads_all_bundled_plugins(self, registry):
        names = {p.name for p in registry.get_all()}
        assert BUNDLED_PLUGINS <= names, f"missing bundled plugins: {BUNDLED_PLUGINS - names}"

    @pytest.mark.parametrize("plugin_name", sorted(BUNDLED_PLUGINS))
    def test_each_bundled_plugin_is_builtin_and_valid(self, registry, plugin_name):
        plugin = registry.get_by_name(plugin_name)
        assert plugin is not None
        assert plugin.is_builtin is True
        # Required fields are populated and non-empty.
        assert plugin.name == plugin_name
        assert plugin.display_name
        assert plugin.version
        assert plugin.countries
        assert plugin.collection_prompt
        assert plugin.apply_prompt
        # file_path points at the on-disk yaml.
        assert plugin.file_path.endswith(f"{plugin_name}.yaml")

    def test_get_by_name_unknown_returns_none(self, registry):
        assert registry.get_by_name("does-not-exist") is None

    def test_get_enabled_defaults_to_all(self, registry):
        # Fresh state: every plugin enabled by default.
        assert len(registry.get_enabled()) == len(registry.get_all())

    def test_get_for_country_filters_by_membership(self, registry):
        # SEEK serves AU/NZ; it must appear for AU and not for, say, IN.
        au = {p.name for p in registry.get_for_country("AU")}
        assert "seek" in au
        india = {p.name for p in registry.get_for_country("IN")}
        assert "seek" not in india


# ── Schema validation / parsing ─────────────────────────────────────────────

class TestParsePluginYaml:
    def test_minimal_valid_plugin(self):
        plugin = _parse_plugin_yaml(_minimal_plugin_dict(), "/x/acme.yaml", is_builtin=False)
        assert isinstance(plugin, PluginConfig)
        assert plugin.name == "acme"
        assert plugin.is_builtin is False
        assert plugin.enabled is True
        assert plugin.file_path == "/x/acme.yaml"
        # Optional fields default sensibly.
        assert plugin.description == ""
        assert plugin.requires_login is False
        assert plugin.auth_cookies == []
        assert plugin.filters == []

    @pytest.mark.parametrize("missing", sorted(REQUIRED_FIELDS))
    def test_missing_required_field_raises(self, missing):
        data = _minimal_plugin_dict()
        del data[missing]
        with pytest.raises(ValueError, match="missing required fields"):
            _parse_plugin_yaml(data, "/x/acme.yaml", is_builtin=False)

    def test_auth_cookies_parsed_and_malformed_skipped(self):
        data = _minimal_plugin_dict(auth_cookies=[
            {"name": "sid", "domain": ".acme.example"},
            {"name": "no_domain"},          # malformed → skipped
            {"domain": ".acme.example"},    # malformed → skipped
            "not-a-dict",                   # malformed → skipped
        ])
        plugin = _parse_plugin_yaml(data, "/x/acme.yaml", is_builtin=True)
        assert plugin.auth_cookies == [AuthCookie(name="sid", domain=".acme.example")]

    def test_domain_patterns_parsed_and_malformed_skipped(self):
        data = _minimal_plugin_dict(domain_patterns=[
            {"pattern": "*.acme.example", "normalize_to": "acme.example"},
            {"pattern": "missing-normalize"},  # malformed → skipped
            42,                                # malformed → skipped
        ])
        plugin = _parse_plugin_yaml(data, "/x/acme.yaml", is_builtin=True)
        assert plugin.domain_patterns == [
            DomainPattern(pattern="*.acme.example", normalize_to="acme.example")
        ]

    def test_filters_parsed_with_defaults(self):
        data = _minimal_plugin_dict(filters=[
            {
                "key": "date_posted",
                "label": "Posted within",
                "options": [{"value": "7", "label": "Last 7 days"}],
                "url_param": "fromage",
                "default": "7",
            },
            {"key": "incomplete"},  # no 'label' → skipped
            {"label": "no key"},    # no 'key' → skipped
        ])
        plugin = _parse_plugin_yaml(data, "/x/acme.yaml", is_builtin=True)
        assert len(plugin.filters) == 1
        f = plugin.filters[0]
        assert f.key == "date_posted"
        assert f.type == "select"  # default applied
        assert f.url_param == "fromage"
        assert f.default == "7"


# ── render_collection_prompt: URL building + filter mapping ──────────────────

class TestRenderCollectionPrompt:
    def _plugin(self, **over) -> PluginConfig:
        base = {
            "search_url": "https://acme.example/{title}-jobs/in-{location}",
            "collection_prompt": "GO TO: {search_url} for {title} in {location} (max {max_jobs})",
        }
        base.update(over)
        return _parse_plugin_yaml(
            _minimal_plugin_dict(**base),
            "/x/acme.yaml",
            is_builtin=True,
        )

    def test_substitutes_title_location_maxjobs(self):
        plugin = self._plugin()
        out = plugin.render_collection_prompt(["Engineer"], ["Sydney"], 20)
        assert "https://acme.example/Engineer-jobs/in-Sydney" in out
        assert "for Engineer in Sydney" in out
        assert "max 20" in out

    def test_empty_titles_and_locations(self):
        plugin = self._plugin()
        out = plugin.render_collection_prompt([], [], 5)
        # title/location render as empty strings, no crash.
        assert "https://acme.example/-jobs/in-" in out

    def test_explicit_filter_appended_with_question_mark(self):
        plugin = self._plugin(filters=[
            {"key": "date_posted", "label": "x", "url_param": "fromage", "default": "7"},
        ])
        out = plugin.render_collection_prompt(["Eng"], ["NYC"], 10, filters={"date_posted": "3"})
        assert "?fromage=3" in out  # user-supplied value wins over default

    def test_filter_appended_with_ampersand_when_url_has_query(self):
        plugin = self._plugin(
            search_url="https://acme.example/{title}?daterange=7",
            filters=[{"key": "jt", "label": "x", "url_param": "jt", "default": "fulltime"}],
        )
        out = plugin.render_collection_prompt(["Eng"], ["NYC"], 10, filters={"jt": "contract"})
        assert "&jt=contract" in out

    def test_defaults_used_when_filters_none(self):
        plugin = self._plugin(filters=[
            {"key": "date_posted", "label": "x", "url_param": "fromage", "default": "7"},
        ])
        out = plugin.render_collection_prompt(["Eng"], ["NYC"], 10)  # filters=None
        assert "?fromage=7" in out

    def test_filter_without_url_param_is_ignored(self):
        plugin = self._plugin(filters=[
            {"key": "k", "label": "x", "default": "v"},  # no url_param
        ])
        out = plugin.render_collection_prompt(["Eng"], ["NYC"], 10)
        assert "?" not in out.split("https://acme.example")[1].split(" ")[0]

    def test_empty_filter_value_skipped(self):
        plugin = self._plugin(filters=[
            {"key": "date_posted", "label": "x", "url_param": "fromage", "default": "7"},
        ])
        # Explicit empty string → not appended.
        out = plugin.render_collection_prompt(["Eng"], ["NYC"], 10, filters={"date_posted": ""})
        assert "fromage" not in out

    def test_multiple_titles_joined(self):
        plugin = _parse_plugin_yaml(
            _minimal_plugin_dict(
                search_url="https://acme.example/q={title}",
                collection_prompt="titles={titles} locations={locations}",
            ),
            "/x/acme.yaml", is_builtin=True,
        )
        out = plugin.render_collection_prompt(["A", "B"], ["X", "Y"], 5)
        assert "titles=A, B" in out
        assert "locations=X, Y" in out


# ── render_apply_prompt + _format_profile ────────────────────────────────────

class TestRenderApplyPrompt:
    def _plugin(self) -> PluginConfig:
        return _parse_plugin_yaml(
            _minimal_plugin_dict(
                apply_prompt=(
                    "URL={job_url} TITLE={job_title} CO={company} "
                    "RESUME={resume_path}\nPROFILE:\n{profile}\nQA:\n{qa_bank}\n"
                    "CL={cover_letter} MEM={memories}"
                ),
            ),
            "/x/acme.yaml", is_builtin=True,
        )

    def test_full_substitution(self):
        plugin = self._plugin()
        job = {"url": "https://j/1", "title": "SWE", "company": "Acme"}
        out = plugin.render_apply_prompt(
            job,
            profile={"name": "Jane"},
            qa_bank={"Why?": "Because", "Empty": ""},
            resume_path="/r.pdf",
            cover_letter="Dear team",
            memories="prefers remote",
        )
        assert "URL=https://j/1" in out
        assert "TITLE=SWE" in out
        assert "CO=Acme" in out
        assert "RESUME=/r.pdf" in out
        assert "Name: Jane" in out
        assert "Q: Why?\nA: Because" in out
        # Empty answers excluded from the rendered Q&A bank.
        assert "Empty" not in out
        assert "CL=Dear team" in out
        assert "MEM=prefers remote" in out

    def test_missing_job_keys_default_to_empty(self):
        plugin = self._plugin()
        out = plugin.render_apply_prompt({}, profile={}, qa_bank={})
        assert "URL= " in out or "URL=" in out
        assert "QA:\n\n" in out  # qa_str empty


class TestFormatProfile:
    def test_empty_profile_is_blank(self):
        assert _format_profile({}) == ""

    def test_rich_profile_renders_all_lines(self):
        profile = {
            "name": "Jane Doe",
            "email": "jane@x.com",
            "phone": "5551234",
            "phone_country_code": "+1",
            "address": {"city": "NYC", "state": "NY", "zip": "10001", "country": "USA"},
            "work_authorization": "Citizen",
            "notice_period": "2 weeks",
            "nationality": "US",
            "years_of_experience": 7,
            "education": {"degree": "BS CS", "school": "MIT", "graduation": "2018"},
            "skills": ["Python", "AWS"],
            "salary_expectation": {"min": 100000, "max": 150000, "currency": "USD", "period": "annual"},
        }
        out = _format_profile(profile)
        assert "Name: Jane Doe" in out
        assert "Email: jane@x.com" in out
        assert "Phone: +15551234" in out
        assert "Location: NYC, NY 10001 USA" in out
        assert "Work Authorization: Citizen" in out
        assert "Notice Period: 2 weeks" in out
        assert "Nationality: US" in out
        assert "Experience: 7 years" in out
        assert "Education: BS CS from MIT (2018)" in out
        assert "Skills: Python, AWS" in out
        # Salary formatted with thousands separators.
        assert "Salary: USD 100,000-150,000 (annual)" in out

    def test_salary_default_period(self):
        out = _format_profile({"salary_expectation": {"min": 1000, "max": 2000, "currency": "EUR"}})
        assert "(annual)" in out

    def test_partial_address_and_no_salary(self):
        # No 'city' → location line omitted; no salary min → salary line omitted.
        out = _format_profile({"name": "X", "address": {"state": "CA"}, "salary_expectation": {}})
        assert out == "Name: X"


# ── Loading edge cases: malformed / missing files ────────────────────────────

class TestLoadYamlFile:
    def test_non_dict_yaml_returns_none(self, registry, tmp_path):
        p = tmp_path / "list.yaml"
        p.write_text("- just\n- a\n- list\n")
        assert registry._load_yaml_file(p, is_builtin=False) is None

    def test_malformed_yaml_returns_none(self, registry, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("name: acme\n  bad: : indentation:\n")
        assert registry._load_yaml_file(p, is_builtin=False) is None

    def test_valid_yaml_missing_fields_returns_none(self, registry, tmp_path):
        # _parse raises ValueError → _load_yaml_file swallows and returns None.
        p = tmp_path / "incomplete.yaml"
        p.write_text("name: acme\ndisplay_name: Acme\n")
        assert registry._load_yaml_file(p, is_builtin=False) is None

    def test_missing_file_returns_none(self, registry, tmp_path):
        assert registry._load_yaml_file(tmp_path / "nope.yaml", is_builtin=False) is None

    def test_valid_file_loads(self, registry, tmp_path):
        p = tmp_path / "ok.yaml"
        p.write_text(yaml.safe_dump(_minimal_plugin_dict()))
        plugin = registry._load_yaml_file(p, is_builtin=False)
        assert plugin is not None and plugin.name == "acme"


# ── Community plugins, enable/disable, state persistence ─────────────────────

class TestCommunityAndState:
    def test_community_plugin_discovered(self, data_dir):
        community = data_dir / "plugins"
        community.mkdir(parents=True, exist_ok=True)
        (community / "custom.yaml").write_text(
            yaml.safe_dump(_minimal_plugin_dict(name="custom", display_name="Custom"))
        )
        reg = PluginRegistry()
        plugin = reg.get_by_name("custom")
        assert plugin is not None
        assert plugin.is_builtin is False

    def test_community_does_not_override_builtin(self, data_dir):
        # A community plugin reusing a builtin name must NOT replace the builtin.
        community = data_dir / "plugins"
        community.mkdir(parents=True, exist_ok=True)
        (community / "seek.yaml").write_text(
            yaml.safe_dump(_minimal_plugin_dict(name="seek", display_name="FAKE SEEK"))
        )
        reg = PluginRegistry()
        assert reg.get_by_name("seek").display_name == "SEEK"
        assert reg.get_by_name("seek").is_builtin is True

    def test_set_enabled_persists_and_filters(self, registry, data_dir):
        assert registry.set_enabled("seek", False) is True
        assert registry.get_by_name("seek").enabled is False
        assert "seek" not in {p.name for p in registry.get_enabled()}
        # State file written.
        state = json.loads((data_dir / "plugin_state.json").read_text())
        assert state["seek"] is False

    def test_set_enabled_unknown_returns_false(self, registry):
        assert registry.set_enabled("ghost", False) is False

    def test_state_applied_on_reload(self, registry, data_dir):
        registry.set_enabled("reed", False)
        # New registry instance reads persisted state.
        reg2 = PluginRegistry()
        assert reg2.get_by_name("reed").enabled is False

    def test_corrupt_state_file_ignored(self, data_dir):
        (data_dir / "plugin_state.json").write_text("{ not json")
        # Should not raise; plugins remain enabled.
        reg = PluginRegistry()
        assert reg.get_by_name("seek").enabled is True

    def test_get_for_country_excludes_disabled(self, registry):
        registry.set_enabled("seek", False)
        assert "seek" not in {p.name for p in registry.get_for_country("AU")}

    def test_get_for_country_all_keyword(self, registry, data_dir):
        community = data_dir / "plugins"
        community.mkdir(parents=True, exist_ok=True)
        (community / "global.yaml").write_text(
            yaml.safe_dump(_minimal_plugin_dict(name="global", countries=["ALL"]))
        )
        reg = PluginRegistry()
        assert "global" in {p.name for p in reg.get_for_country("ZZ")}

    def test_reload_rediscovers(self, registry, data_dir):
        community = data_dir / "plugins"
        community.mkdir(parents=True, exist_ok=True)
        (community / "late.yaml").write_text(
            yaml.safe_dump(_minimal_plugin_dict(name="late"))
        )
        assert registry.get_by_name("late") is None  # added after construction
        registry.reload()
        assert registry.get_by_name("late") is not None


# ── import_plugin / remove_plugin ────────────────────────────────────────────

class TestImportRemove:
    def test_import_valid_plugin(self, registry, data_dir, tmp_path):
        src = tmp_path / "mine.yaml"
        src.write_text(yaml.safe_dump(_minimal_plugin_dict(name="mine")))
        plugin = registry.import_plugin(str(src))
        assert plugin.name == "mine"
        # Copied into community dir.
        dest = data_dir / "plugins" / "mine.yaml"
        assert dest.exists()
        assert plugin.file_path == str(dest)
        assert registry.get_by_name("mine") is not None

    def test_import_missing_file_raises(self, registry, tmp_path):
        with pytest.raises(FileNotFoundError):
            registry.import_plugin(str(tmp_path / "ghost.yaml"))

    @pytest.mark.parametrize("suffix", [".txt", ".json", ""])
    def test_import_bad_suffix_raises(self, registry, tmp_path, suffix):
        src = tmp_path / f"plugin{suffix}"
        src.write_text("name: x")
        with pytest.raises(ValueError, match="must be a .yaml"):
            registry.import_plugin(str(src))

    def test_import_invalid_yaml_raises(self, registry, tmp_path):
        src = tmp_path / "broken.yaml"
        src.write_text("name: x\ndisplay_name: y\n")  # missing required → parse fails
        with pytest.raises(ValueError, match="failed to parse"):
            registry.import_plugin(str(src))

    def test_import_cannot_override_builtin(self, registry, tmp_path):
        src = tmp_path / "seek.yaml"
        src.write_text(yaml.safe_dump(_minimal_plugin_dict(name="seek")))
        with pytest.raises(ValueError, match="Cannot override built-in"):
            registry.import_plugin(str(src))

    def test_import_accepts_yml_suffix(self, registry, data_dir, tmp_path):
        src = tmp_path / "mine.yml"
        src.write_text(yaml.safe_dump(_minimal_plugin_dict(name="mine2")))
        plugin = registry.import_plugin(str(src))
        assert plugin.name == "mine2"

    def test_remove_community_plugin(self, registry, data_dir, tmp_path):
        src = tmp_path / "mine.yaml"
        src.write_text(yaml.safe_dump(_minimal_plugin_dict(name="mine")))
        registry.import_plugin(str(src))
        dest = data_dir / "plugins" / "mine.yaml"
        assert dest.exists()
        assert registry.remove_plugin("mine") is True
        assert registry.get_by_name("mine") is None
        assert not dest.exists()

    def test_remove_unknown_returns_false(self, registry):
        assert registry.remove_plugin("ghost") is False

    def test_remove_builtin_raises(self, registry):
        with pytest.raises(ValueError, match="Cannot remove built-in"):
            registry.remove_plugin("seek")

    def test_remove_community_with_missing_file(self, registry, data_dir, tmp_path):
        # If the backing file was deleted out from under us, removal still succeeds.
        src = tmp_path / "mine.yaml"
        src.write_text(yaml.safe_dump(_minimal_plugin_dict(name="mine")))
        registry.import_plugin(str(src))
        (data_dir / "plugins" / "mine.yaml").unlink()
        assert registry.remove_plugin("mine") is True
        assert registry.get_by_name("mine") is None
