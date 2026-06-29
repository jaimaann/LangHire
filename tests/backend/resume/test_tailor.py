"""Unit tests for the resume tailoring engine (backend/resume/tailor.py).

The engine parses a PDF (via pymupdf/fitz), extracts logical sections, sends
selected sections to an LLM for rewriting under character limits, and emits a
freshly-generated PDF + markdown sidecar.

Testing strategy:
- Pure helpers (_url_hash, _wrap_text, _identify_tailorable_sections) tested directly.
- _extract_sections tested against real, minimal PDFs built in-memory with fitz.
- The LLM is always mocked (create_llm + ainvoke) — NO network.
- File outputs land in the isolated tmp data dir via the ``data_dir`` fixture.
"""
import hashlib
import json
from pathlib import Path

import fitz
import pytest

import resume.tailor as tailor
from resume.tailor import (
    _MEASURE_FONT,
    _BODY_SIZE,
    _TEXT_WIDTH,
    _BULLET_INDENT,
    _PAGE_HEIGHT,
    _PAGE_WIDTH,
    _extract_sections,
    _generate_fresh_pdf,
    _generate_tailored_text,
    _identify_tailorable_sections,
    _is_bullet,
    _is_entry_header,
    _split_entries,
    _strip_bullet,
    _url_hash,
    _wrap_text,
    delete_tailored_resume,
    get_tailored_content,
    get_tailored_resume_path,
    refine_resume,
    tailor_resume,
)


# ── PDF builders ─────────────────────────────────────────────────────────────

def _make_pdf(path: Path, blocks: list[tuple[float, float, str]]):
    """Write a single-page PDF placing each (x, y, text) string as a block.

    fitz groups text into blocks; placing each string far apart vertically keeps
    them in distinct blocks so _extract_sections can treat them independently.
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for x, y, text in blocks:
        page.insert_text(fitz.Point(x, y), text, fontsize=11)
    doc.save(str(path))
    doc.close()


def _resume_blocks() -> list[tuple[float, float, str]]:
    """A canonical resume with skills, experience, education sections."""
    return [
        (40, 60, "Skills"),
        (40, 90, "Python, AWS, Docker"),
        (40, 140, "Experience"),
        (40, 170, "Senior Engineer"),
        (40, 195, "Acme Corp"),
        (40, 220, "- Built scalable systems"),
        (40, 280, "Education"),
        (40, 310, "BS Computer Science, MIT"),
    ]


@pytest.fixture
def resume_pdf(tmp_path):
    p = tmp_path / "resume.pdf"
    _make_pdf(p, _resume_blocks())
    return p


# ── Pure helpers ─────────────────────────────────────────────────────────────

class TestUrlHash:
    def test_deterministic_and_truncated(self):
        h = _url_hash("https://example.com/job/1")
        assert h == hashlib.md5(b"https://example.com/job/1").hexdigest()[:12]
        assert len(h) == 12

    def test_distinct_urls_distinct_hashes(self):
        assert _url_hash("a") != _url_hash("b")


class TestWrapText:
    def test_short_text_single_line(self):
        assert _wrap_text("hello world", 500, 9) == ["hello world"]

    def test_wraps_long_text(self):
        text = "word " * 50
        lines = _wrap_text(text.strip(), 100, 9)
        assert len(lines) > 1
        assert all(line.strip() for line in lines)

    def test_empty_text(self):
        assert _wrap_text("", 100, 9) == []

    def test_single_word_longer_than_width_still_emitted(self):
        # A word wider than max_chars cannot be split; it occupies its own line.
        lines = _wrap_text("supercalifragilisticexpialidocious", 20, 9)
        assert lines == ["supercalifragilisticexpialidocious"]


class TestIdentifyTailorableSections:
    SECTIONS = [
        {"section_type": "skills", "text": "s"},
        {"section_type": "overview", "text": "o"},
        {"section_type": "experience", "text": "e"},
        {"section_type": "education", "text": "edu"},
    ]

    @pytest.mark.parametrize("options,expected", [
        ({"skills": True}, ["skills"]),
        ({"overview": True}, ["overview"]),
        ({"experience": True}, ["experience"]),
        ({"skills": True, "experience": True}, ["skills", "experience"]),
        ({}, []),
        ({"skills": False}, []),
        ({"education": True}, []),  # education is never tailorable
    ])
    def test_filtering(self, options, expected):
        result = _identify_tailorable_sections(self.SECTIONS, options)
        assert [s["section_type"] for s in result] == expected


# ── _extract_sections against real PDFs ──────────────────────────────────────

class TestExtractSections:
    def test_extracts_known_sections(self, resume_pdf):
        doc = fitz.open(str(resume_pdf))
        sections = _extract_sections(doc)
        doc.close()
        types = [s["section_type"] for s in sections]
        assert "skills" in types
        assert "experience" in types
        assert "education" in types

    def test_section_has_content_and_metadata(self, resume_pdf):
        doc = fitz.open(str(resume_pdf))
        sections = _extract_sections(doc)
        doc.close()
        skills = next(s for s in sections if s["section_type"] == "skills")
        assert "Python" in skills["text"]
        assert skills["char_count"] == len(skills["text"])
        assert len(skills["bbox"]) == 4
        assert skills["content_blocks"]

    def test_no_headers_yields_no_sections(self, tmp_path):
        p = tmp_path / "plain.pdf"
        _make_pdf(p, [(40, 60, "Just some plain text"), (40, 120, "More text here")])
        doc = fitz.open(str(p))
        sections = _extract_sections(doc)
        doc.close()
        assert sections == []

    def test_header_with_no_content_is_dropped(self, tmp_path):
        # A trailing header with no following content blocks is not emitted.
        p = tmp_path / "trailing.pdf"
        _make_pdf(p, [
            (40, 60, "Skills"),
            (40, 90, "Python"),
            (40, 700, "Education"),  # header but nothing after it
        ])
        doc = fitz.open(str(p))
        sections = _extract_sections(doc)
        doc.close()
        types = [s["section_type"] for s in sections]
        assert "skills" in types
        assert "education" not in types

    def test_header_synonyms_map_to_canonical_type(self, tmp_path):
        p = tmp_path / "syn.pdf"
        _make_pdf(p, [
            (40, 60, "Summary"),
            (40, 90, "A seasoned engineer"),
            (40, 150, "Technologies"),
            (40, 180, "Go, Rust"),
        ])
        doc = fitz.open(str(p))
        sections = _extract_sections(doc)
        doc.close()
        types = {s["section_type"] for s in sections}
        assert "overview" in types  # "Summary"
        assert "skills" in types    # "Technologies"

    def test_empty_pdf_yields_no_sections(self, tmp_path):
        p = tmp_path / "empty.pdf"
        doc = fitz.open()
        doc.new_page(width=612, height=792)
        doc.save(str(p))
        doc.close()
        doc = fitz.open(str(p))
        assert _extract_sections(doc) == []
        doc.close()


# ── _generate_tailored_text (LLM mocked) ─────────────────────────────────────

class _FakeLLM:
    """Stand-in for a browser_use chat model. Records the prompt it receives."""

    def __init__(self, response):
        self._response = response
        self.last_messages = None

    async def ainvoke(self, messages):
        self.last_messages = messages
        return self._response


class _Completion:
    def __init__(self, completion):
        self.completion = completion


class _Content:
    def __init__(self, content):
        self.content = content


def _patch_llm(monkeypatch, response, settings=None):
    """Patch load_llm_settings + create_llm so the engine uses a fake LLM."""
    fake = _FakeLLM(response)
    monkeypatch.setattr(tailor, "load_llm_settings", lambda: settings or {"provider": "anthropic"})
    monkeypatch.setattr(tailor, "create_llm", lambda s: fake)
    return fake


SECTIONS = [
    {"section_type": "skills", "text": "Python, AWS", "char_count": 11},
    {"section_type": "overview", "text": "Engineer with 5 years", "char_count": 21},
]


class TestGenerateTailoredText:
    async def test_happy_path_completion_attr(self, monkeypatch):
        resp = _Completion(json.dumps({"0": "Python, GCP", "1": "Cloud engineer"}))
        fake = _patch_llm(monkeypatch, resp)
        out = await _generate_tailored_text(SECTIONS, "Cloud role", {})
        assert out == {0: "Python, GCP", 1: "Cloud engineer"}
        # Prompt was assembled with the section originals + char limits.
        prompt = fake.last_messages[0].content
        assert "Python, AWS" in prompt
        assert "max 11 characters" in prompt
        assert "Cloud role" in prompt

    async def test_uses_content_attr_when_no_completion(self, monkeypatch):
        resp = _Content(json.dumps({"0": "ok", "1": "fine"}))
        _patch_llm(monkeypatch, resp)
        out = await _generate_tailored_text(SECTIONS, "jd", {})
        assert out == {0: "ok", 1: "fine"}

    async def test_falls_back_to_str_for_unknown_response(self, monkeypatch):
        # An object lacking completion/content (and non-str content) → str(response).
        resp = json.dumps({"0": "x", "1": "y"})  # plain string, no attrs
        _patch_llm(monkeypatch, resp)
        out = await _generate_tailored_text(SECTIONS, "jd", {})
        assert out == {0: "x", 1: "y"}

    async def test_oversized_output_is_truncated(self, monkeypatch):
        long = "z" * 100
        resp = _Completion(json.dumps({"0": long, "1": "ok"}))
        _patch_llm(monkeypatch, resp)
        out = await _generate_tailored_text(SECTIONS, "jd", {})
        assert len(out[0]) == 11  # truncated to char_count
        assert out[0] == "z" * 11

    async def test_json_embedded_in_prose_is_extracted(self, monkeypatch):
        resp = _Completion('Here you go: {"0": "a", "1": "b"} — done!')
        _patch_llm(monkeypatch, resp)
        out = await _generate_tailored_text(SECTIONS, "jd", {})
        assert out == {0: "a", 1: "b"}

    async def test_missing_section_keys_omitted(self, monkeypatch):
        resp = _Completion(json.dumps({"0": "only zero"[:11]}))
        _patch_llm(monkeypatch, resp)
        out = await _generate_tailored_text(SECTIONS, "jd", {})
        assert 0 in out
        assert 1 not in out

    async def test_no_provider_raises(self, monkeypatch):
        monkeypatch.setattr(tailor, "load_llm_settings", lambda: {"provider": ""})
        with pytest.raises(ValueError, match="No LLM configured"):
            await _generate_tailored_text(SECTIONS, "jd", {})

    async def test_non_json_response_raises(self, monkeypatch):
        resp = _Completion("I cannot help with that.")
        _patch_llm(monkeypatch, resp)
        with pytest.raises(ValueError, match="did not return valid JSON"):
            await _generate_tailored_text(SECTIONS, "jd", {})

    async def test_refinement_note_included_in_prompt(self, monkeypatch):
        resp = _Completion(json.dumps({"0": "x", "1": "y"}))
        fake = _patch_llm(monkeypatch, resp)
        await _generate_tailored_text(SECTIONS, "jd", {}, refinement="Be concise")
        assert "ADDITIONAL INSTRUCTION: Be concise" in fake.last_messages[0].content

    async def test_long_job_description_truncated_to_3000(self, monkeypatch):
        resp = _Completion(json.dumps({"0": "x", "1": "y"}))
        fake = _patch_llm(monkeypatch, resp)
        jd = "Q" * 5000
        await _generate_tailored_text(SECTIONS, jd, {})
        prompt = fake.last_messages[0].content
        assert "Q" * 3000 in prompt
        assert "Q" * 3001 not in prompt


# ── tailor_resume orchestration (LLM mocked, real PDF) ───────────────────────

class TestTailorResume:
    def _configure(self, monkeypatch, data_dir, resume_pdf, llm_resp,
                   provider="anthropic", profile=None):
        """Wire up settings/profile/LLM for an end-to-end tailor_resume call."""
        monkeypatch.setattr(tailor, "load_settings", lambda: {"resume_path": str(resume_pdf)})
        monkeypatch.setattr(tailor, "load_llm_settings", lambda: {"provider": provider})
        monkeypatch.setattr(tailor, "create_llm", lambda s: _FakeLLM(llm_resp))
        if profile is not None:
            import core.config as config
            monkeypatch.setattr(config, "load_profile", lambda: profile)

    async def test_end_to_end_produces_pdf_and_md(self, monkeypatch, data_dir, resume_pdf):
        resp = _Completion(json.dumps({"0": "Python, GCP", "1": "- Led cloud migration"}))
        self._configure(monkeypatch, data_dir, resume_pdf, resp,
                        profile={"name": "Jane", "email": "j@x.com"})
        result = await tailor_resume(
            "https://job/1", "Cloud role", {"skills": True, "experience": True}
        )
        assert Path(result["path"]).exists()
        assert result["path"].endswith(".pdf")
        assert result["sections_total"] >= 1
        assert result["sections_tailored"] >= 1
        # Markdown sidecar written and retrievable.
        content = get_tailored_content("https://job/1")
        assert content is not None
        assert "## SKILLS" in content["content"] or "## EXPERIENCE" in content["content"]

    async def test_missing_resume_path_raises(self, monkeypatch, data_dir):
        monkeypatch.setattr(tailor, "load_settings", lambda: {"resume_path": ""})
        with pytest.raises(FileNotFoundError):
            await tailor_resume("u", "jd", {"skills": True})

    async def test_nonexistent_resume_file_raises(self, monkeypatch, data_dir, tmp_path):
        monkeypatch.setattr(tailor, "load_settings", lambda: {"resume_path": str(tmp_path / "nope.pdf")})
        with pytest.raises(FileNotFoundError):
            await tailor_resume("u", "jd", {"skills": True})

    async def test_no_tailorable_sections_raises(self, monkeypatch, data_dir, resume_pdf):
        resp = _Completion("{}")
        self._configure(monkeypatch, data_dir, resume_pdf, resp)
        # Options select nothing → no tailorable sections.
        with pytest.raises(ValueError, match="No tailorable sections"):
            await tailor_resume("u", "jd", {})

    async def test_llm_tailors_nothing_raises(self, monkeypatch, data_dir, resume_pdf):
        # LLM returns valid JSON but with no matching section keys → empty result.
        resp = _Completion(json.dumps({"99": "irrelevant"}))
        self._configure(monkeypatch, data_dir, resume_pdf, resp)
        with pytest.raises(ValueError, match="could not tailor any sections"):
            await tailor_resume("u", "jd", {"skills": True, "experience": True})

    async def test_profile_load_failure_is_tolerated(self, monkeypatch, data_dir, resume_pdf):
        resp = _Completion(json.dumps({"0": "Python, GCP"}))
        self._configure(monkeypatch, data_dir, resume_pdf, resp)
        import core.config as config
        def _boom():
            raise RuntimeError("profile broken")
        monkeypatch.setattr(config, "load_profile", _boom)
        # Profile errors are swallowed; tailoring still succeeds.
        result = await tailor_resume("https://job/2", "jd", {"skills": True})
        assert Path(result["path"]).exists()

    async def test_refine_resume_delegates(self, monkeypatch, data_dir, resume_pdf):
        resp = _Completion(json.dumps({"0": "Python, GCP"}))
        self._configure(monkeypatch, data_dir, resume_pdf, resp,
                        profile={"name": "Jane"})
        result = await refine_resume("https://job/3", "jd", "make it punchy", {"skills": True})
        assert Path(result["path"]).exists()


# ── Content lifecycle: get / delete / path ───────────────────────────────────

class TestContentLifecycle:
    def test_get_content_missing_returns_none(self, data_dir):
        assert get_tailored_content("https://absent") is None

    def test_get_path_missing_returns_none(self, data_dir):
        assert get_tailored_resume_path("https://absent") is None

    def test_delete_missing_returns_false(self, data_dir):
        assert delete_tailored_resume("https://absent") is False

    async def test_get_and_delete_after_tailoring(self, monkeypatch, data_dir, resume_pdf):
        resp = _Completion(json.dumps({"0": "Python, GCP"}))
        monkeypatch.setattr(tailor, "load_settings", lambda: {"resume_path": str(resume_pdf)})
        monkeypatch.setattr(tailor, "load_llm_settings", lambda: {"provider": "anthropic"})
        monkeypatch.setattr(tailor, "create_llm", lambda s: _FakeLLM(resp))
        url = "https://job/lifecycle"
        await tailor_resume(url, "jd", {"skills": True})

        assert get_tailored_resume_path(url) is not None
        content = get_tailored_content(url)
        assert content is not None and content["path"] is not None

        assert delete_tailored_resume(url) is True
        assert get_tailored_content(url) is None
        assert get_tailored_resume_path(url) is None
        # Second delete is a no-op.
        assert delete_tailored_resume(url) is False

    def test_get_content_without_pdf_returns_none_path(self, data_dir):
        # Markdown present but no PDF → path is None.
        from resume.tailor import _get_tailored_dir
        url = "https://job/mdonly"
        md = _get_tailored_dir() / f"{_url_hash(url)}.md"
        md.write_text("## SKILLS\n\nPython", encoding="utf-8")
        content = get_tailored_content(url)
        assert content is not None
        assert content["path"] is None
        assert "Python" in content["content"]


# ── Font-metric wrapping ─────────────────────────────────────────────────────

class TestFontMetricWrapping:
    """_wrap_text now measures with real font metrics, not a char-width guess."""

    def test_every_wrapped_line_fits_real_width(self):
        # A long realistic sentence wrapped to a narrow column.
        text = (
            "Led a cross functional team of engineers to design and ship a "
            "highly scalable distributed data processing platform handling "
            "billions of events per day across multiple AWS regions reliably."
        )
        width = 200.0
        lines = _wrap_text(text, width, _BODY_SIZE)
        assert len(lines) > 1
        for line in lines:
            assert _MEASURE_FONT.text_length(line, _BODY_SIZE) <= width

    def test_wrapping_is_tighter_than_old_estimate(self):
        # With real metrics the produced lines should pack close to the width
        # without exceeding it (the old 0.52 char-width estimate could overflow
        # or under-fill). Verify no line exceeds and at least one line uses
        # most of the available width.
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"
        width = 150.0
        lines = _wrap_text(text, width, _BODY_SIZE)
        assert all(_MEASURE_FONT.text_length(l, _BODY_SIZE) <= width for l in lines)
        assert max(_MEASURE_FONT.text_length(l, _BODY_SIZE) for l in lines) > width * 0.6

    def test_word_wider_than_width_emitted_alone(self):
        # A single token that overflows is still emitted (cannot be split).
        long = "x" * 300
        lines = _wrap_text(long, 80.0, _BODY_SIZE)
        assert lines == [long]


# ── Bullet / entry detection ─────────────────────────────────────────────────

class TestBulletDetection:
    @pytest.mark.parametrize("line", [
        "· dotted bullet",
        "- dash bullet",
        "• round bullet",
        "* asterisk bullet",
        "– en dash bullet",
        "— em dash bullet",
        "‣ triangle bullet",
        "● filled circle",
        "1. numbered bullet",
        "2) numbered paren",
        "  • indented bullet",
        "a. lettered",
    ])
    def test_recognizes_bullet_styles(self, line):
        assert _is_bullet(line) is True

    @pytest.mark.parametrize("line", [
        "Senior Engineer",
        "Acme Corp",
        "2019 - 2022",
        "",
        "Just a sentence with no marker.",
    ])
    def test_non_bullets_rejected(self, line):
        assert _is_bullet(line) is False

    @pytest.mark.parametrize("line,expected", [
        ("• built things", "built things"),
        ("- did work", "did work"),
        ("1. first item", "first item"),
        ("2) second item", "second item"),
        ("plain text", "plain text"),
    ])
    def test_strip_bullet(self, line, expected):
        assert _strip_bullet(line) == expected

    @pytest.mark.parametrize("line", [
        "2019 - 2022",
        "Jan 2019 – Present",
        "Senior Engineer — Acme Corp",
        "Backend Engineer @ Globex",
        "Developer at Initech",
    ])
    def test_entry_header_detection(self, line):
        assert _is_entry_header(line) is True

    @pytest.mark.parametrize("line", [
        "• a bullet is not a header",
        "Just a normal sentence here",
        "",
    ])
    def test_non_entry_headers(self, line):
        assert _is_entry_header(line) is False


class TestSplitEntries:
    def test_blank_line_separates_entries(self):
        content = "Title A\n• did x\n\nTitle B\n• did y"
        entries = _split_entries(content)
        assert len(entries) == 2
        assert entries[0][0] == "Title A"
        assert entries[1][0] == "Title B"

    def test_new_header_after_bullets_starts_entry(self):
        # No blank line, but a non-bullet line after bullets begins a new entry.
        content = "Title A\n• did x\nTitle B\n• did y"
        entries = _split_entries(content)
        assert len(entries) == 2

    def test_entry_header_pattern_splits_without_bullets(self):
        # Bullet-less resume using "Title — Company" headers.
        content = "Engineer — Acme\nShipped a product\nEngineer — Globex\nBuilt a tool"
        entries = _split_entries(content)
        assert len(entries) == 2
        assert entries[0][0] == "Engineer — Acme"
        assert entries[1][0] == "Engineer — Globex"


# ── _generate_fresh_pdf layout / overflow ────────────────────────────────────

def _make_sections(skills_text="", experience_text=""):
    secs = []
    if skills_text:
        secs.append({"section_type": "skills", "text": skills_text,
                     "char_count": len(skills_text)})
    if experience_text:
        secs.append({"section_type": "experience", "text": experience_text,
                     "char_count": len(experience_text)})
    return secs


def _all_text_spans(doc):
    """Yield (page, span_dict) for every text span in the document."""
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    yield page, span


class TestGenerateFreshPdf:
    def test_no_text_drawn_off_page(self, tmp_path):
        long_exp = "\n".join(
            f"Engineer {i} — Company {i}\n• " + ("achievement detail " * 8)
            for i in range(40)
        )
        out = tmp_path / "out.pdf"
        _generate_fresh_pdf(_make_sections(experience_text=long_exp), {},
                            "Jane Doe", "jane@x.com", "BS CS, MIT", out)
        doc = fitz.open(str(out))
        try:
            for page, span in _all_text_spans(doc):
                x0, y0, x1, y1 = span["bbox"]
                assert y1 <= _PAGE_HEIGHT, f"text below page bottom: {y1}"
                assert x1 <= _PAGE_WIDTH + 1, f"text past right edge: {x1}"
                assert y0 >= 0 and x0 >= 0
        finally:
            doc.close()

    def test_enough_content_produces_multiple_pages(self, tmp_path):
        long_exp = "\n".join(
            f"Role {i} — Org {i}\n• " + ("did meaningful impactful work " * 6)
            for i in range(50)
        )
        out = tmp_path / "multi.pdf"
        _generate_fresh_pdf(_make_sections(experience_text=long_exp), {},
                            "Jane Doe", "jane@x.com", "", out)
        doc = fitz.open(str(out))
        try:
            assert doc.page_count > 1
        finally:
            doc.close()

    def test_short_content_single_page(self, tmp_path):
        out = tmp_path / "short.pdf"
        _generate_fresh_pdf(
            _make_sections(skills_text="Python, AWS",
                           experience_text="Engineer — Acme\n• Built systems"),
            {}, "Jane", "jane@x.com", "BS CS", out,
        )
        doc = fitz.open(str(out))
        try:
            assert doc.page_count == 1
        finally:
            doc.close()

    def test_bullet_continuation_lines_share_hanging_indent(self, tmp_path):
        # A long bullet wraps; continuation lines align under the first line's
        # text, not back at the left margin.
        bullet = "• " + ("scaled the platform to handle massive traffic " * 6)
        out = tmp_path / "hang.pdf"
        _generate_fresh_pdf(_make_sections(experience_text=f"Role — Org\n{bullet}"),
                            {}, "Jane", "", "", out)
        doc = fitz.open(str(out))
        try:
            spans = [s for _, s in _all_text_spans(doc)
                     if "scaled" in s["text"] or "platform" in s["text"]]
            assert len(spans) > 1  # the bullet wrapped
            xs = sorted({round(s["bbox"][0]) for s in spans})
            # Bullet glyph line and continuation lines both indented past margin.
            assert all(x > 36 for x in xs)
        finally:
            doc.close()
