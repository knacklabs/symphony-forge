# The look of Forge's own screens

Forge has two things that people look at: the board page and the /forge pane in Claude Code.
This file says how each one looks. It is about Forge's own screens only. A client app has its own
design system and theme.

## Who looks, and why

An engineering manager and developers of teams that build with Forge. They come to do a task: see
what needs them, read a plan, follow a build. So the screens are calm, easy to scan and stable.
A refresh keeps the screen: nothing moves, closes or loads again over content that is already
shown.

## Rules for both

- Plain English. No IDs, hashes or jargon, no "unknown", "0s" or empty values. A story's own key
  may show small beside its title on the board.
- No emoji. Marks are simple shapes, and two states differ in shape or lightness as well as colour.
- Text contrast is at least 4.5 to 1 in light and in dark.
- Motion is rare and short (200 ms or less) and stops when the person asks for reduced motion.
  Nothing animates on a refresh.
- Controls are real buttons and links that the keyboard reaches, with a visible focus ring.

## The board page

The values live in `src/forge/board_app/tokens.css`. The approved design language is in
`docs/board-design/`.

- Font: the system font (`-apple-system, "Segoe UI", system-ui, sans-serif`). Sizes: title 24 px,
  region 17 px, body 14 px, label 12 px.
- Light colours: ground `#F4F5F2`, surface `#FFFFFF`, line `#E2E4E0`, ink `#15171A`, second ink
  `#4A4F57`. The header bar is dark (`#15171A`) in both themes.
- State colours: moving `#1D4ED8`, needs you `#B54708`, stuck `#9F1239`, ready `#0F766E`,
  waiting `#8A9096`.
- Spacing steps: 4, 8, 12, 16, 24, 32, 48 px. Corners: cards 6 px, tags 3 px.
- Laptop first. A half-screen window must stay readable. There is no phone layout.

## The /forge pane

Claude Code draws the pane with its own parts, so Forge does not choose the font. The approved
screens are in `docs/design/FORGE-PANE-1/`.

- One job: what runs now on this laptop, with one line at the top if something needs the person.
- Terminal: text, boxes and buttons only, in the terminal's own font and colours. One or two lines
  for each run.
- Claude desktop app: a richer drawing with the same words in the same order. Each run is a card.
  A filled dot means running and a hollow dot means waiting. Two meters show the laptop's places in
  use. A test run has a progress bar. The selected card shows the last output lines and the two
  buttons.
- Desktop colours, light: ground `#faf9f5`, card `#ffffff`, soft fill `#f0eee6`, line `#e3e0d6`,
  text `#141413`, second text `#5c5a52`, marks and bars `#1d4ed8`, banner fill `#fbe9d7` with text
  `#7a3410` and `#4a2a12`. Where Claude Code offers its own theme colours, the pane uses those, so
  that it follows the person's light or dark theme.
- The word "Loading" shows only before the first content. After that, the last rows stay.
