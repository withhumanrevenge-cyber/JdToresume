"""Reading job postings out of HTML.

1. `find_job_posting`: many career pages embed the posting as structured data (schema.org `JobPosting` in a
   `<script type="application/ld+json">` tag) so that Google for Jobs can index it. That's the cleanest source.
2. `html_to_text`: otherwise, the readable text of the page, without scripts, navigation, headers and footers.
"""

from __future__ import annotations

import html as html_lib
import json
from html.parser import HTMLParser
from typing import Any

from app.features.jobs.ingestion.raw import RawJob, compose_text

_SKIP = {"script", "style", "noscript", "svg", "template", "head", "nav", "header", "footer", "form", "button"}
_BLOCK = {"p", "div", "section", "article", "main", "br", "tr", "ul", "ol", "table",
          "h1", "h2", "h3", "h4", "h5", "h6", "dl", "dt", "dd", "blockquote"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skip_depth += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK or tag == "li":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """Readable plain text: one paragraph per line, list items as "- item", whitespace tidied."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    text = "\n".join(line for line in lines if line and line != "-")
    return text.strip()


# --------------------------------------------------------------------------- schema.org JobPosting

class _JsonLdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._inside = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and (dict(attrs).get("type") or "").lower() == "application/ld+json":
            self._inside = True
            self.blocks.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._inside = False

    def handle_data(self, data: str) -> None:
        if self._inside:
            self.blocks[-1] += data


def find_job_posting(html: str) -> dict[str, Any] | None:
    """The first schema.org JobPosting embedded in the page, if any."""
    collector = _JsonLdCollector()
    collector.feed(html)
    for block in collector.blocks:
        try:
            data = json.loads(block)
        except ValueError:
            continue  # broken structured data is common; just try the next block
        for item in _walk(data):
            types = item.get("@type")
            if types == "JobPosting" or (isinstance(types, list) and "JobPosting" in types):
                return item
    return None


def _walk(data: Any):
    """Every JSON object in a JSON-LD document, including those nested in lists and "@graph"."""
    if isinstance(data, dict):
        yield data
        for value in data.values():
            if isinstance(value, (dict, list)):
                yield from _walk(value)
    elif isinstance(data, list):
        for item in data:
            yield from _walk(item)


def raw_job_from_posting(posting: dict[str, Any]) -> RawJob:
    company = posting.get("hiringOrganization")
    salary = posting.get("baseSalary")
    extra = {
        "Employment type": _as_text(posting.get("employmentType")),
        "Salary": _salary_text(salary) if isinstance(salary, dict) else None,
        "Remote": "yes" if str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE" else None,
    }
    sections = [html_to_text(html_lib.unescape(str(posting.get("description", ""))))]
    for field, heading in (("responsibilities", "Responsibilities"), ("qualifications", "Qualifications"),
                           ("skills", "Skills"), ("experienceRequirements", "Experience")):
        value = _as_text(posting.get(field))
        if value:
            sections.append(f"{heading}:\n{html_to_text(html_lib.unescape(value))}")
    return RawJob(
        text=compose_text(
            title=_as_text(posting.get("title")),
            company=_as_text(company.get("name")) if isinstance(company, dict) else _as_text(company),
            location=_location_text(posting.get("jobLocation")),
            body="\n\n".join(section for section in sections if section),
            extra=extra,
        ),
        source="embedded_data",
    )


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v) or None
    return str(value).strip() or None


def _location_text(value: Any) -> str | None:
    places = value if isinstance(value, list) else [value]
    names = []
    for place in places:
        address = place.get("address") if isinstance(place, dict) else None
        if isinstance(address, dict):
            parts = [address.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
            names.append(", ".join(str(p.get("name", p)) if isinstance(p, dict) else str(p) for p in parts if p))
    return "; ".join(n for n in names if n) or None


def _salary_text(salary: dict[str, Any]) -> str | None:
    value = salary.get("value")
    if isinstance(value, dict):
        low, high, unit = value.get("minValue"), value.get("maxValue"), value.get("unitText")
        amount = f"{low}–{high}" if low and high else str(low or high or value.get("value") or "")
        return " ".join(p for p in (salary.get("currency"), amount, f"per {unit.lower()}" if unit else None) if p) or None
    return _as_text(value)
