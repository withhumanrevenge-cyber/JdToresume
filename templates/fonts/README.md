# templates/fonts: vendored OFL fonts (Phase 1)

The renderer loads every font in this folder (system fonts are off, so output is identical on every host).
To add: Inter or Source Sans 3 (the `modern` template's sans), Noto Sans + Noto Sans Devanagari/Tamil/... for
non-Latin names. Commit each font's OFL licence file next to it. Then switch `templates/modern.typ` to the sans.
