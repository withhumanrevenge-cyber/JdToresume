"""Contact details never reach the LLM. The pipeline sends placeholders and the renderer restores them."""

from __future__ import annotations

import re

from app.llm.schemas import CareerProfile, ContactDetails

PLACEHOLDERS = {
    "full_name": "{{FULL_NAME}}",
    "email": "{{EMAIL}}",
    "phone": "{{PHONE}}",
    "city": "{{CITY}}",
}


class PIILeak(RuntimeError):
    """Raised before a request is sent if it contains the user's contact details."""


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def assert_no_contact_pii(request_text: str, contact: ContactDetails) -> None:
    """Fail closed if the user's own email, phone, full name or profile links appear in an outgoing request.

    Third-party text such as a recruiter email inside a job posting is allowed; only the user's details are checked.
    """
    lowered = request_text.lower()
    if contact.email and contact.email.lower() in lowered:
        raise PIILeak("email")
    if contact.phone:
        phone = _digits(contact.phone)
        if len(phone) >= 7 and phone[-7:] in _digits(request_text):
            raise PIILeak("phone")
    if contact.full_name and len(contact.full_name.split()) >= 2 and contact.full_name.lower() in lowered:
        raise PIILeak("full_name")
    for link in contact.links:
        handle = link.lower().rstrip("/").split("/")[-1]
        if len(handle) >= 4 and link.lower() in lowered:
            raise PIILeak("link")


def _link_core(link: str) -> str:
    """'https://www.github.com/jdoe/' -> 'github.com/jdoe' (what to search for in free text)."""
    return re.sub(r"^(?:https?://)?(?:www\.)?", "", link.strip(), flags=re.I).rstrip("/")


def redact_profile(profile: CareerProfile, contact: ContactDetails) -> dict:
    """The profile as the LLM sees it: no project links (the renderer takes them from the profile), and the
    user's own email, phone and profile links replaced by placeholders anywhere they appear in free text."""
    data = profile.model_dump(mode="json")
    for project in data["projects"]:
        project["link"] = None
    replacements = [(contact.email, PLACEHOLDERS["email"])] if contact.email else []
    if contact.phone:
        replacements.append((contact.phone, PLACEHOLDERS["phone"]))
    replacements += [(_link_core(link), f"{{{{LINK_{i}}}}}") for i, link in enumerate(contact.links) if _link_core(link)]

    def scrub(value):
        if isinstance(value, str):
            for needle, placeholder in replacements:
                value = re.sub(re.escape(needle), placeholder, value, flags=re.I)
            return value
        if isinstance(value, list):
            return [scrub(v) for v in value]
        if isinstance(value, dict):
            return {k: scrub(v) for k, v in value.items()}
        return value

    return scrub(data)


def restore_placeholders(text: str, contact: ContactDetails) -> str:
    """Put the person's real details back where the LLM wrote placeholders (at render time only)."""
    values = {"full_name": contact.full_name, "email": contact.email, "phone": contact.phone or "", "city": contact.city or ""}
    for field, placeholder in PLACEHOLDERS.items():
        text = text.replace(placeholder, values[field])
    for i, link in enumerate(contact.links):  # profile links were sent as {{LINK_0}}, {{LINK_1}}, ...
        text = text.replace(f"{{{{LINK_{i}}}}}", link)
    return text
