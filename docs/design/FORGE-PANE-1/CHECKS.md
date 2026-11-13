# Design checks

These checks ran on 13 Nov 2026 on the nine pages in `src/` and their images.

## What was checked

- Rendered in Chrome with Playwright 1.55.0 at each page's own size, at two times scale. No page
  scrolls sideways or down: each page's scroll width and height equal its frame.
- The coordinator looked at desktop-running.png and pane-needs-you.png on screen.
- Words: every line uses the plan's exact words. No IDs, no "unknown", no "0s", no empty values,
  no emoji. Example repo names are made up.
- Contrast, by the colour values used: desktop text #141413 and #3d3b35 and #5c5a52 on #faf9f5,
  #ffffff and #f0eee6; banner text #7a3410 and #4a2a12 on #fbe9d7; terminal text #e7e9ee,
  #c5cbd6 and #a4abb8 on #15171c and #252a33; needs-you text #f2b866 on #15171c. All pairs are
  above 4.5 to 1.
- Running and waiting differ in shape as well as colour: a filled dot and a hollow dot.
- Controls are real buttons, 44 px high.
- No motion is drawn. The plan sets that times count up each second and that nothing else moves.

## Not checked

- The pane in the real Claude desktop app and in a real terminal. Claude Code draws the pane with
  its own parts, so the plan has a by-hand check on screen before the merge.
- The dark look of the desktop app. The plan names the colours for it.
- An automated accessibility run. The pages are static pictures of a pane that Claude Code draws.
