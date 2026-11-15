# calado brand

- **Corporate colors:** white `#ffffff` and blue `#006CFF`. Ink `#0b1424` for text; no other accent colors.
- **Logo:** the word `calado` in lowercase, extra-bold Inter, tight tracking. `cala` in ink, `do` in `#006CFF`. Source: `logo-calado.svg`; in the app: `app/src/ui/Logo.tsx`.
- **Principles** (from `docs/brand-references/`): hairline 1px borders, no gradients or shadows, 8px card radius, `tabular-nums` for dates and amounts, sober factual English copy. Blue is reserved for actions, selection and the logo's "do".

## Mark and favicon
- **Mark:** a white "c" on a `#006CFF` rounded square. *Calado* means cut-out: the circle is open on one side and the dot in the opening is the match. Source: `mark-calado.svg`; PNGs in `app/assets/` (`mark.png` for the in-app logo, `favicon.png` for the browser tab, set in `app/app.json`).
- The in-app `Logo` component shows the mark next to the wordmark; pass `mark={false}` for the wordmark alone.
