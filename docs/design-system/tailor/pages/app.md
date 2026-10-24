# Tailor web app: overrides to MASTER.md

These rules override `../MASTER.md` for the signed-in web app (`apps/web`). Everything not listed here follows Master.
The tokens live in `apps/web/src/app/globals.css`; every pair below was measured (WCAG 2.2 relative luminance).

## Colour

| Change | Why |
|--------|-----|
| Body text `#0F172A` (slate-900) instead of `#0C4A6E` | Long reading (letters, bullets) is calmer in near-black; brand blue stays for actions. 16.8:1 on the background |
| Input borders `#7896AE` (light) / `#5B7896` (dark) instead of `#BAE6FD` | Form controls need 3:1 against their surface (WCAG 1.4.11). Measured 3.1:1 and 3.65:1. `#BAE6FD` stays for decorative borders (`--border` `#CFE3F1`) |
| Green is for status only (`--success`, `--success-muted`), not the CTA | One primary action per screen, always the brand blue. Green and amber mark measured results (ATS check, match status) |
| Added `--warning-muted` / `--destructive-muted` pairs | Tinted alerts and badges with 5.3:1+ text; shadcn's 10%-tint defaults sat at ~4.4:1 |
| Destructive button is solid red with `--destructive-foreground` | White on `#DC2626` is 4.8:1; in dark mode dark text on `#F87171` |

Dark mode is designed alongside light (same token names). Key pairs: text 15.5:1, secondary text 8.5:1, primary on
card 7.8:1.

## Type

Plus Jakarta Sans for everything (Master), plus Geist Mono only for "What the ATS sees" (it shows raw extracted text).

## Interaction

- Buttons and inputs are 40 px tall by default, 44 px for the main action (shadcn ships 32 px).
- Tabs 40 px; inactive tab labels use `--muted-foreground` (6.5:1), not 60% foreground.
- Status is never colour alone: every badge, step and requirement says it in words too.
- Long waits (resume parsing, job reading, generation) explain themselves and show steps, never a bare spinner.
- `prefers-reduced-motion` turns transitions and animations off.
