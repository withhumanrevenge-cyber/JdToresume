"""Renderer + ATS round-trip tests. Rendering runs the real Typst compiler (local, no network)."""

from __future__ import annotations

import io
from collections import Counter
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.features.rendering.ats_roundtrip import (
    ExtractedText,
    check_pdf,
    check_text,
    extract,
    main as ats_cli,
    term_present,
)
from app.features.rendering.document import (
    RenderOptions,
    UnknownReferenceError,
    build_resume_document,
    format_range,
)
from app.features.rendering.typst_renderer import count_pages, render_fit, render_pdf
from app.llm.schemas import Bullet, CareerProfile, ContactDetails, JobSpec, Keyword, TailoredResume

FIXTURES = Path(__file__).parent / "fixtures"
TEMPLATES = ["classic", "modern"]
LIGATURE_GLYPHS = "ﬀﬁﬂﬃﬄﬅﬆ"

# fact id -> MatchReport.fact_relevance score for the sample job
RELEVANCE = {
    "f-nw-1": 3, "f-nw-2": 3, "f-nw-3": 3, "f-nw-4": 1, "f-nw-5": 1,
    "f-co-1": 2, "f-co-2": 2, "f-co-3": 1, "f-co-4": 0,
    "f-fa-1": 0, "f-fa-2": 1,
    "f-pr-1": 2, "f-pr-2": 1,
}


def _load(model, name):
    return model.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def profile() -> CareerProfile:
    return _load(CareerProfile, "sample_profile.json")


@pytest.fixture
def contact() -> ContactDetails:
    return _load(ContactDetails, "sample_contact.json")


@pytest.fixture
def resume() -> TailoredResume:
    return _load(TailoredResume, "sample_tailored_resume.json")


@pytest.fixture
def job() -> JobSpec:
    return _load(JobSpec, "sample_job.json")


def _render(resume, profile, contact, template="classic", page_size=None):
    options = RenderOptions(
        template=template,
        page_size=page_size or RenderOptions.page_size_for_region(profile.preferences.region),
    )
    document = build_resume_document(resume, profile, contact, options)
    return render_pdf(document, template), document


def _sections(document) -> list[str]:
    return [section["kind"] for section in document["sections"]]


# --------------------------------------------------------------------------- templates + round trip

@pytest.mark.parametrize("template", TEMPLATES)
def test_template_renders_and_passes_roundtrip(template, resume, profile, contact, job):
    pdf, document = _render(resume, profile, contact, template)

    assert pdf.startswith(b"%PDF")
    assert count_pages(pdf) == 1
    assert len(pdf) < 1_000_000
    assert b"/StructTreeRoot" in pdf  # tagged PDF (Typst >= 0.14 tags by default)
    metadata = PdfReader(io.BytesIO(pdf)).metadata
    assert metadata.title == "Jordan Rivera – Resume"
    assert metadata.author == "Jordan Rivera"

    check = check_pdf(pdf, contact, _sections(document), job)
    assert check.parse_ok, check.issues
    assert check.extractors_agree and check.extractor_agreement >= 0.95
    assert check.contact_found
    assert check.sections_found == ["summary", "experience", "skills", "projects", "education", "certifications"]
    assert check.date_issues == []
    assert check.keywords_missing == ["Java", "gRPC", "microservices"]
    assert check.keyword_coverage == pytest.approx(8 / 11)
    assert check.must_have_coverage == pytest.approx(4 / 5)  # r5 (Java, Spring Boot) has no evidence


@pytest.mark.parametrize("template", TEMPLATES)
def test_render_is_deterministic(template, resume, profile, contact):
    first, _ = _render(resume, profile, contact, template)
    second, _ = _render(resume, profile, contact, template)
    assert first == second


@pytest.mark.parametrize("template", TEMPLATES)
def test_no_ligature_glyphs_in_extracted_text(template, resume, profile, contact):
    pdf, _ = _render(resume, profile, contact, template)
    extracted = extract(pdf)
    for text in (extracted.primary, extracted.secondary):
        assert "certified" in text
        assert "offline-first sync workflow" in text
        assert not set(LIGATURE_GLYPHS) & set(text)


def test_glyph_check_flags_ligatures_private_use_and_tiny_text():
    text = "Jordan Rivera\njordan.rivera@example.com\nSummary\nAWS certiﬁed engineer "
    check = check_text(ExtractedText(text, text.replace("", "\x02"), min_font_size=6.5), None, ["summary"], None)
    assert not check.parse_ok
    joined = " ".join(check.issues)
    assert "ligature glyphs" in joined
    assert "pdfminer: private-use glyphs" in joined
    assert "pypdf: unmapped glyphs" in joined
    assert "smaller than 8 pt" in joined


def test_name_in_script_without_embedded_font_fails_roundtrip(resume, profile, contact):
    # Typst renders tofu without a warning when no available font covers a script; the round trip must catch it.
    # TODO(phase-1): flip this once Noto Sans (Indic and other scripts) is vendored under templates/fonts/.
    devanagari = contact.model_copy(update={"full_name": "राहुल शर्मा"})
    pdf, _ = _render(resume, profile, devanagari)
    check = check_pdf(pdf, devanagari, [], None)
    assert not check.parse_ok
    assert "name not found near the top" in check.issues


def test_user_text_is_not_evaluated_as_markup(resume, profile, contact):
    tricky = 'Shipped C# and *nix tooling for #ops at $5/day, see @ref <x> "quoted" [link] \\ done.'
    resume.experience[0].bullets[0] = Bullet(text=tricky, source_fact_ids=["f-nw-1"], targets_requirement_ids=[])
    pdf, _ = _render(resume, profile, contact)
    assert tricky in extract(pdf).primary.replace("\n", " ")


# --------------------------------------------------------------------------- page size

def test_page_size_letter_vs_a4(resume, profile, contact):
    letter, _ = _render(resume, profile, contact, page_size="us-letter")
    a4, _ = _render(resume, profile, contact, page_size="a4")
    letter_box = PdfReader(io.BytesIO(letter)).pages[0].mediabox
    a4_box = PdfReader(io.BytesIO(a4)).pages[0].mediabox
    assert (float(letter_box.width), float(letter_box.height)) == pytest.approx((612, 792), abs=0.5)
    assert (float(a4_box.width), float(a4_box.height)) == pytest.approx((595.28, 841.89), abs=0.5)


@pytest.mark.parametrize(("region", "expected"), [
    ("US", "us-letter"), ("CA", "us-letter"), ("UK", "a4"), ("IN", "a4"), ("DE", "a4"), ("OTHER", "a4"),
])
def test_page_size_derived_from_region(region, expected, profile):
    profile.preferences.region = region
    assert RenderOptions.page_size_for_region(region) == expected
    assert RenderOptions.for_profile(profile, template="modern").page_size == expected


# --------------------------------------------------------------------------- document builder

def test_unknown_experience_id_raises(resume, profile, contact):
    resume.experience[1].experience_id = "exp-does-not-exist"
    with pytest.raises(UnknownReferenceError, match="exp-does-not-exist"):
        build_resume_document(resume, profile, contact, RenderOptions(page_size="a4"))


@pytest.mark.parametrize("mutate", [
    lambda r: setattr(r.projects[0], "project_id", "proj-nope"),
    lambda r: setattr(r.education[0], "education_id", "edu-nope"),
    lambda r: r.certification_ids.append("cert-nope"),
    lambda r: r.experience[0].bullets[0].source_fact_ids.append("f-nope"),
    lambda r: r.summary_source_fact_ids.append("f-nope"),
])
def test_other_unknown_references_raise(mutate, resume, profile, contact):
    mutate(resume)
    with pytest.raises(UnknownReferenceError, match="nope"):
        build_resume_document(resume, profile, contact, RenderOptions(page_size="a4"))


def test_header_fields_come_from_profile(resume, profile, contact):
    # The LLM never writes a title; whatever it says in prose, the header is the profile's.
    profile.experience[0].title = "Payments Platform Engineer II"
    resume.summary = "Senior Staff Engineer and head of payments with 6 years building services in Go."
    pdf, document = _render(resume, profile, contact)

    experience = next(s for s in document["sections"] if s["kind"] == "experience")
    first = experience["entries"][0]
    assert first["title"] == "Payments Platform Engineer II"
    assert first["org"] == "Northwind Payments"
    assert first["location"] == "Austin, TX"
    assert first["dates"] == "Mar 2022 – Present"
    assert [e["title"] for e in experience["entries"]] == ["Payments Platform Engineer II", "Software Engineer",
                                                            "Junior Developer"]

    text = extract(pdf).primary
    assert "Payments Platform Engineer II, Northwind Payments" in text
    assert "Senior Staff Engineer, Northwind Payments" not in text


def test_project_education_and_certification_headers_come_from_profile(resume, profile, contact):
    _, document = _render(resume, profile, contact)
    by_kind = {s["kind"]: s for s in document["sections"]}
    project = by_kind["projects"]["entries"][0]
    assert (project["title"], project["dates"]) == ("ledgerlite", "Jan 2023 – Jun 2023")
    assert project["link"] == {"text": "github.com/jrivera-example/ledgerlite",
                               "url": "https://github.com/jrivera-example/ledgerlite"}
    education = by_kind["education"]["entries"][0]
    assert education["title"] == "B.S., Computer Science"
    assert education["org"] == "University of Texas at Austin"
    assert education["dates"] == "Aug 2013 – May 2017"
    assert education["detail"] == "GPA 3.6/4.0"
    assert by_kind["certifications"]["items"] == [
        "AWS Certified Developer – Associate, Amazon Web Services, Apr 2023",
        "Certified Kubernetes Application Developer (CKAD), The Linux Foundation, Feb 2024",
    ]


def test_contact_goes_into_header_with_visible_links(resume, profile, contact):
    _, document = _render(resume, profile, contact)
    header = document["header"]
    assert header["name"] == "Jordan Rivera"
    assert [item["text"] for item in header["contact"]] == [
        "jordan.rivera@example.com", "+1 (555) 010-4477", "Austin, TX",
        "linkedin.com/in/jordan-rivera-example", "github.com/jrivera-example",
    ]
    assert header["contact"][3]["url"] == "https://www.linkedin.com/in/jordan-rivera-example/"
    assert header["contact"][4]["url"] == "https://github.com/jrivera-example"


def test_sections_follow_section_order_and_skip_empty(resume, profile, contact):
    resume.section_order = ["education", "experience", "summary", "certifications", "projects", "experience"]
    resume.certification_ids = []
    resume.projects = []
    pdf, document = _render(resume, profile, contact)
    assert _sections(document) == ["education", "experience", "summary"]  # skills not in order: omitted
    check = check_pdf(pdf, contact, _sections(document), None)
    assert check.parse_ok, check.issues
    assert check.sections_found == ["education", "experience", "summary"]


@pytest.mark.parametrize(("start", "end", "expected"), [
    ("2022-03", None, "Mar 2022 – Present"),
    ("2019-06", "2022-02", "Jun 2019 – Feb 2022"),
    ("2023-04-15", "2023-04", "Apr 2023"),
    (None, "2017-05", "May 2017"),
    ("2015", "2017", "2015 – 2017"),
    (None, None, ""),
])
def test_format_range(start, end, expected):
    assert format_range(start, end) == expected


@pytest.mark.parametrize("bad", ["March 2020", "2020-13", "03/2020"])
def test_format_range_rejects_unparseable_dates(bad):
    with pytest.raises(ValueError):
        format_range(bad, None)


# --------------------------------------------------------------------------- fit to page

def _score(bullet: Bullet) -> int:
    return max((RELEVANCE.get(f, 0) for f in bullet.source_fact_ids), default=0)


def test_fit_to_page_trims_long_resume_to_one_page(resume, profile, contact, job):
    long = resume.model_copy(deep=True)
    for role in long.experience:
        role.bullets = [b.model_copy(update={"text": f"{b.text} Variant {n}."}) for n in range(4) for b in role.bullets]
    options = RenderOptions.for_profile(profile)
    assert count_pages(render_pdf(build_resume_document(long, profile, contact, options), "classic")) > 1
    before = [len(r.bullets) for r in long.experience]

    pdf, trimmed = render_fit(long, profile, contact, options, page_limit=1, relevance=RELEVANCE)

    assert count_pages(pdf) == 1
    assert [len(r.bullets) for r in long.experience] == before  # input untouched
    assert all(len(role.bullets) >= 1 for role in trimmed.experience)
    assert len(trimmed.projects[0].bullets) == 1

    kept = Counter(b.text for role in trimmed.experience for b in role.bullets)
    dropped = [b for role in long.experience for b in role.bullets if not kept[b.text]]
    assert dropped
    # Lowest relevance goes first: an entry that still has spare bullets never keeps one scoring below a dropped one.
    worst_dropped = max(_score(b) for b in dropped)
    for role in trimmed.experience:
        if len(role.bullets) > 1:
            assert all(_score(b) >= worst_dropped for b in role.bullets)
    # Every score-3 bullet survives this trim.
    assert all(_score(b) < 3 for b in dropped)

    check = check_pdf(pdf, contact, list(trimmed.section_order), job)
    assert check.parse_ok, check.issues


def test_fit_breaks_ties_with_last_bullet_of_oldest_role(resume, profile, contact):
    flat = {fact_id: 1 for fact_id in RELEVANCE}  # every bullet ties
    long = resume.model_copy(deep=True)
    for role in long.experience:
        role.bullets = [b.model_copy(update={"text": f"{b.text} Variant {n}."}) for n in range(4) for b in role.bullets]
    options = RenderOptions.for_profile(profile)

    _, trimmed = render_fit(long, profile, contact, options, page_limit=1, relevance=flat)

    by_id = {r.experience_id: r for r in trimmed.experience}
    oldest, newest = by_id["exp-fabrikam"], by_id["exp-northwind"]
    assert len(oldest.bullets) == 1  # oldest role is trimmed to the floor first
    assert oldest.bullets[0].text == long.experience[2].bullets[0].text  # its first bullet stays
    assert len(newest.bullets) == len(long.experience[0].bullets)  # newest role untouched


def test_fit_leaves_a_fitting_resume_alone(resume, profile, contact):
    options = RenderOptions.for_profile(profile, template="modern")
    pdf, trimmed = render_fit(resume, profile, contact, options, page_limit=1, relevance=RELEVANCE)
    assert count_pages(pdf) == 1
    assert trimmed == resume


# --------------------------------------------------------------------------- keyword matching + check failures

@pytest.mark.parametrize(("term", "text", "present"), [
    ("Java", "JavaScript and TypeScript", False),
    ("Java", "Java, JavaScript", True),
    ("java", "Built services in JAVA 17", True),
    ("JavaScript", "javascript dashboards", True),
    ("C", "C++ and C#", False),
    ("C++", "Modern C++ and Go", True),
    ("Go", "Golang and Google", False),
    ("API", "Designed REST APIs", True),
    ("real-time", "real time pipelines", True),
    ("Spring Boot", "Spring\nBoot services", True),
])
def test_keyword_matching_is_word_boundary_aware(term, text, present):
    assert term_present(term, text) is present


def test_java_keyword_not_counted_from_javascript_in_pdf(resume, profile, contact, job):
    pdf, document = _render(resume, profile, contact)

    def coverage(*terms: str) -> float | None:
        keywords = [Keyword(term=t, synonyms=[], weight=1) for t in terms]
        return check_pdf(pdf, contact, _sections(document), job.model_copy(update={"keywords": keywords})).keyword_coverage

    assert coverage("Java") == 0.0
    assert coverage("JavaScript") == 1.0
    assert coverage("Java", "JavaScript", "TypeScript", "Go") == 0.75


def test_roundtrip_flags_out_of_order_experience(resume, profile, contact):
    resume.experience.reverse()
    pdf, document = _render(resume, profile, contact)
    check = check_pdf(pdf, contact, _sections(document), None)
    assert not check.parse_ok
    assert any("reverse-chronological" in issue for issue in check.date_issues)


def test_roundtrip_flags_wrong_contact_and_missing_section(resume, profile, contact):
    pdf, document = _render(resume, profile, contact)
    other = contact.model_copy(update={"email": "someone.else@example.com", "phone": "+1 (555) 010-9999"})
    check = check_pdf(pdf, other, [*_sections(document), "projects"], None)
    assert not check.parse_ok and not check.contact_found
    assert "email not found near the top" in check.issues
    assert "phone not found near the top" in check.issues

    resume.projects = []
    pdf, document = _render(resume, profile, contact)
    check = check_pdf(pdf, contact, ["summary", "experience", "projects"], None)
    assert "section 'projects' not found" in check.issues


def test_roundtrip_flags_non_standard_dates():
    text = ("Jordan Rivera\njordan.rivera@example.com\nExperience\nEngineer, Acme\n03/2021 - 2023-05\n"
            "Engineer, Initech\nJan 2022 – Mar 2020\nEducation\nB.S., Somewhere\n2013 – 2017")
    check = check_text(ExtractedText(text, text, 10.5), None, ["experience", "education"], None)
    assert any("non-standard date" in issue for issue in check.date_issues)
    assert any("ends before it starts" in issue for issue in check.date_issues)
    assert not any("2013" in issue for issue in check.date_issues)


def test_cli_prints_text_and_check(tmp_path, capsys, resume, profile, contact):
    pdf, _ = _render(resume, profile, contact, "modern")
    path = tmp_path / "Jordan-Rivera-Resume.pdf"
    path.write_bytes(pdf)

    code = ats_cli([str(path), "--email", contact.email, "--name", contact.full_name, "--phone", contact.phone,
                    "--sections", "summary,experience,skills"])

    out = capsys.readouterr().out
    assert code == 0
    assert "===== pdfminer.six =====" in out and "===== check =====" in out
    assert "jordan.rivera@example.com" in out
    assert '"parse_ok": true' in out
