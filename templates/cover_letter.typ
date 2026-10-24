// Cover letter template: same look as the classic resume, single column, ATS-safe.
//
// Input: `sys.inputs.letter`, a JSON string built by
// server/app/features/rendering/cover_letter.py::build_cover_letter_document (placeholders already
// replaced with the real name and contact details). Every value is inserted as a string, never
// evaluated as markup.
//
// Same rules as the resume (.claude/skills/ats-compliance §2): contact details in the body, not the
// page header/footer; ligatures and hyphenation off; visible URLs; page size from the data.

#let data = json(bytes(sys.inputs.letter))
#let header = data.header
#let sep = "  |  "

#set document(title: header.name + " – Cover Letter", author: header.name, date: none)
#set page(paper: data.page.paper, margin: 0.9in, header: none, footer: none)
#set text(font: "Libertinus Serif", size: 11pt, lang: "en", ligatures: false, hyphenate: false)
#set par(justify: false, leading: 0.6em, spacing: 1.1em)

// `box` keeps a URL or phone number on one line; it is emitted as ordinary text, not a PDF text box.
#let contact-item(item) = box(if item.url == none { item.text } else { link(item.url, item.text) })

// ---------------------------------------------------------------- sender (body, not page header)
#align(center)[
  #text(size: 18pt, weight: "bold", header.name)
  #linebreak()
  #header.contact.map(contact-item).join(sep)
]
#v(1.2em)

// ---------------------------------------------------------------- the letter
#{
  data.date
  parbreak()
  if data.recipient.len() > 0 {
    data.recipient.join(linebreak())
    parbreak()
  }
  data.salutation
  parbreak()
  for paragraph in data.paragraphs {
    paragraph
    parbreak()
  }
  data.closing
  linebreak()
  data.signature
}
