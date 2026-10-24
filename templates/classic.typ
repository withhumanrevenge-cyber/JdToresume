// Classic resume template: single column, serif, ATS-safe.
//
// Input: `sys.inputs.resume`, a JSON string built by
// server/app/features/rendering/document.py::build_resume_document (dates are already
// "Mon YYYY – Mon YYYY", headers already resolved from the CareerProfile). Every value is
// inserted as a string, never evaluated as markup, so text like "C#" or "*nix" stays literal.
//
// ATS rules (.claude/skills/ats-compliance §2): one column read top to bottom; standard
// section headings; contact details in the body, not the page header/footer; no tables,
// boxes, shapes or icons; ligatures and hyphenation off (a hyphenated "Kuber-netes" breaks
// keyword search just like a "ﬁ" glyph does); real "•" bullets; visible URLs; page size
// from the data; dates on the same line as the entry they belong to (a right-aligned date
// is split off into its own text block by pdfminer and read out of order).
//
// Fonts: Libertinus Serif ships embedded with Typst. The renderer disables system fonts, so
// the output is identical on every host.
// TODO(phase-1): vendor an OFL sans (Inter or Source Sans 3) under templates/fonts/.

#let data = json(bytes(sys.inputs.resume))
#let header = data.header
#let sep = "  |  "

#set document(title: header.name + " – Resume", author: header.name, date: none)
#set page(paper: data.page.paper, margin: 0.6in, header: none, footer: none)
#set text(font: "Libertinus Serif", size: 10.5pt, lang: "en", ligatures: false, hyphenate: false)
#set par(justify: false, leading: 0.5em, spacing: 0.6em)
#set list(marker: [•], indent: 0.15em, body-indent: 0.5em, spacing: 0.42em)
#show heading: set text(size: 12pt, weight: "bold")
#show heading: set block(above: 1.05em, below: 0.6em)

// `box` here is Typst's inline "don't break inside" container, not a PDF text box: it keeps a
// URL or phone number on one line and is emitted as ordinary text.
#let contact-item(item) = box(if item.url == none { item.text } else { link(item.url, item.text) })

#let entry(e) = {
  let meta = ()
  if e.dates != "" { meta.push(e.dates) }
  if e.location != none { meta.push(e.location) }
  if e.link != none { meta.push(link(e.link.url, e.link.text)) }
  block(sticky: true, above: 0.85em, below: 0.45em)[
    #text(weight: "bold", e.title)#if e.org != none [, #e.org]
    #if meta.len() > 0 { linebreak(); emph(meta.join(sep)) }
    #if e.detail != none { linebreak(); e.detail }
  ]
  if e.bullets.len() > 0 { list(..e.bullets) }
}

// ---------------------------------------------------------------- header (body, not page header)
#align(center)[
  #text(size: 20pt, weight: "bold", header.name)
  #if header.headline != none { linebreak(); text(size: 11pt, header.headline) }
  #linebreak()
  #header.contact.map(contact-item).join(sep)
]

// ---------------------------------------------------------------- sections, in the order given
#for section in data.sections {
  heading(level: 1, section.heading)
  if section.kind == "summary" {
    par(section.text)
  } else if section.kind in ("experience", "projects", "education") {
    for e in section.entries { entry(e) }
  } else if section.kind == "skills" {
    for group in section.groups {
      block(above: 0.45em, below: 0.45em)[#text(weight: "bold", group.label + ":") #group.items]
    }
  } else if section.kind == "certifications" {
    list(..section.items)
  }
}
