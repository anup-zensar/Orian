# Orion design kit (Shell palette, light theme only)

Paths are relative to `frontend/src/`. Styling and layout only: never change labels, aria-labels, test ids, routes or data fetching. Palette source: [`reference/shell-color-preview.html`](../reference/shell-color-preview.html) (Shell palette given by the client owner).

## 1. Colours: use tokens, never hex in pages

Palette constants live in `theme/orionTheme.ts` (`palette`, `ai`, `cardShadow`, `cardRadius`); semantic sets (RAG, lens, actor, AI badge) in `theme/tokens.ts`. Everything else is a Fluent token (`tokens.*`), already mapped to the palette by `orionTheme`.

| Use | Token / constant |
|---|---|
| Page canvas (#F5F5F5) | `tokens.colorNeutralBackground3` (only the shell sets it) |
| Card / surface (white) | `tokens.colorNeutralBackground1` |
| Row hover / pressed | `colorNeutralBackground1Hover` (#EBEBEB) / `Pressed` (#E0E0E0) |
| Strong text | `colorNeutralForeground1` (#292929) |
| Secondary text | `colorNeutralForeground2` (#424242) |
| Subtle text, captions | `colorNeutralForeground3` (#6B6B6B, palette #757575 darkened for AA on the canvas) |
| Borders | `colorNeutralStroke2` (subtle, cards/dividers), `colorNeutralStroke1` (inputs, #757575) |
| Primary action fill | `colorBrandBackground` (#FFC600, hover #FFCB14, pressed #EBB600); use `<Button appearance="primary">` |
| Text/icon ON yellow | `colorNeutralForegroundOnBrand` (#292929). NEVER white on yellow |
| Selected/active tint | `colorBrandBackground2` (#FFF5DB) + `palette.yellow` indicator bar (>= 3 px) + semibold strong text |
| Links, brand-coloured text | `colorBrandForegroundLink` / `colorBrandForeground1` (#4B78AA); hover/pressed are darker (#3A6190 / #2F5380) so they stay AA |
| Danger / critical text | `colorPaletteRedForeground1` (#B3171A); fills `colorPaletteRedBackground3` (#DD1D21) |
| Checkbox/radio/switch fill | automatic (`colorCompoundBrand*` = #292929) |
| Focus ring | automatic (#292929) |
| Orion / AI accent (purple) | `ai.main` #9A60A4, `ai.tint`, `ai.text`; ONLY for AI badge, Orion panel, Orion-written cards |

Contrast rules (all checked, WCAG AA): dark text on yellow (9.2:1); never yellow text or thin yellow lines on white (1.6:1): yellow is a fill or a thick bar, and the state is also shown by weight/text; blue for links and brand text; red for danger; colour is never the only signal (RAG chips always carry words). Links sit on white cards (4.6:1); on the grey canvas they are 4.2:1, so put text links inside a card.

Semantic colours: `ragColors[rag]` (`foreground` = text-safe on white, `background` = tint, `border` = solid colour for icons/accent bars), `ragSolid[rag]` (solid chip: Red/Green white text, Amber `#292929` text), `lensColors[lens]`, `actorStyles[actor]`, `aiBadgeColors`, `chipStyle(set)` to apply a set to a Badge. For a new status colour add it to `theme/tokens.ts`, not to the page.

## 2. Spacing, type, surfaces

- Page padding 24 px (16 px under 700 px) is set by `AppShell`; pages add none. Gap between page sections: `tokens.spacingVerticalL` (16 px) or `spacingVerticalXL`. Inside cards: `spacingVerticalM` (12 px).
- Font: Arial (Segoe UI fallback), set by the theme. Page title 24 px semibold (via `PageHeader`), card title `Subtitle2` semibold, body 14 px.
- Card = white, 1 px `colorNeutralStroke2`, `cardRadius` (12 px), `cardShadow`. Use `SectionCard`; for a custom surface import `cardRadius`/`cardShadow` from `theme/orionTheme`.
- Radius: controls `tokens.borderRadiusMedium`, nav/list items 8 px, chips `shape="rounded"`.

## 3. Shared components (`components/`)

All props are backward compatible.

- `PageHeader` (`components/PageHeader`): `<PageHeader title subtitle actions as?="h1"|"h2" />`. Title 24 px semibold, subtitle subtle, actions right-aligned and wrapping below when narrow. Sets the document title for h1.
- `SectionCard` (`components/SectionCard`): `<SectionCard title actions id? tone?="ai">...</SectionCard>`. `tone="ai"` adds the purple top line for Orion-written content.
- `KpiTile` (`components/KpiTile`): `<KpiTile label value tone="danger|warning|success|info|neutral" caption? hint? icon? onClick? active? />`. Icon sits in a tinted circle (default icon per tone); clickable tiles are real buttons. Put tiles in `repeat(auto-fit, minmax(200px, 1fr))`.
- `RagChip` (`rag`, `label?`): solid chip with words. `LensChip` (`lens`), `ActorBadge` (`actor`, adds the AI badge for Orion agent), `AiBadge` (purple "AI"), `InsightsCard` (AI card with typed actions).
- `EmptyState` (`message`, `action?`), `ErrorState` (`error`, `onRetry?`), `LoadingState` (`rows?`): use these three for every list/page that can be empty, fail or load.

## 4. Layout kit (`components/layout/`)

Follow the width of the CONTENT (the left nav and the 420 px Orion panel eat width), never the viewport.

```tsx
import { FormGrid, FormFull } from '../../components/layout/FormGrid';
<FormGrid minColWidth={240}>          {/* auto-fill columns, 1 column when narrow */}
  <Field label="Region"><Select>...</Select></Field>
  <FormFull><Field label="Description"><Textarea /></Field></FormFull>   {/* spans the row */}
</FormGrid>
```

```tsx
import { SplitLayout } from '../../components/layout/SplitLayout';
<SplitLayout main={<FormCards />} aside={<AutoScopePanel />} stickyAside />
// main: flex 1 1 520px; aside: flex 1 1 280px, max 380px. The aside drops BELOW the main column when content is narrow.
```

```tsx
import { Toolbar } from '../../components/layout/Toolbar';   // alias: ActionsRow
<Toolbar align="end">                 {/* "start" | "end" | "between"; wraps instead of overflowing */}
  <Button>Cancel</Button><Button appearance="primary">Save</Button>
</Toolbar>
```

```tsx
import { DataTable } from '../../components/DataTable';
<DataTable label="OCET lines" stickyFirstColumn>   {/* scrolls inside its own box, never the page */}
  <Table>...</Table>
</DataTable>
// Soft edge shadow shows there are more columns; optional sticky first column keeps the row name
// visible; header cells and chips never wrap. Aim for at most ~6 visible columns; put secondary
// data in an expanded row or details line.
```

Site-wide, `theme/GlobalStyles.tsx` (mounted once in `main.tsx`) gives every control inside a Fluent `Field` `min-width:0` and `max-width:100%`, makes the Field grid `minmax(0,1fr)`, sets `box-sizing: border-box`, and draws the selected-Tab indicator in yellow. You do not need to repeat that.

Shell (`layout/`): white top bar with a 4 px yellow top accent; left nav 232 px, collapses to an icon rail (tooltips, same links) when the Orion panel is open below 1600 px or the viewport is under 900 px; the panel overlays below 1200 px. The workspace tabs (`features/transitions/TransitionWorkspace.tsx`) use strong text + yellow 3 px underline.

## 5. Rules

1. Every flex/grid child that holds text, tables, selects or inputs gets `minWidth: 0` (grid columns: `minmax(0, 1fr)`). Wide tables scroll inside their own `overflowX: 'auto'` wrapper, never the page.
2. Content breakpoints are never viewport media queries: use `FormGrid`, `SplitLayout`, `flex-wrap`, `repeat(auto-fit, minmax(min(100%, Npx), 1fr))`. Media queries only for the shell.
3. Use `PageHeader` for the title and `SectionCard` for every boxed section; do not draw your own card borders/shadows.
4. No hard-coded hex or rgb in pages: use `tokens.*`, `palette`, `ai`, `ragColors`/`ragSolid`/`lensColors`/`actorStyles`. Do not use `colorBrandBackground` for text, or white text on it.
5. Purple is only for AI/Orion. Red is for danger/critical only. Yellow is for primary actions, selected indicators and accent bars.
6. One primary (yellow) button per view/dialog; the rest secondary or subtle.
7. Keep every label, aria-label, test id and route exactly as they are.

## 6. Checklist for restyling a page

1. Wrap nothing in your own padding; start with `<PageHeader ...>`.
2. Replace ad-hoc boxes with `SectionCard`; KPI numbers with `KpiTile`; statuses with `RagChip`.
3. Replace fixed `repeat(2, ...)`/`1fr 1fr` grids and viewport media queries with `FormGrid` / `SplitLayout` / `Toolbar`.
4. Add `minWidth: 0` to flex/grid children; put wide tables in a scroll wrapper.
5. Remove hex/rgb values and brand-coloured text that is not a link; use the tokens in section 1.
6. Check at 1440x900, 1280x800 with the Orion panel open, and 1024x768: `document.documentElement.scrollWidth === clientWidth`, nothing overlapping, every button fully visible.
7. `tsc -p tsconfig.app.json --noEmit`, `npm run lint`, `prettier --check src`, `npm run build`; no console errors.
