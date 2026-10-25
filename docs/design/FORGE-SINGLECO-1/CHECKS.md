# Design checks

The checks ran on the two artboards in `src/` and their 1440 by 900 images. The fixes went into
the artboards in one pass, and the images were made again with `.forge/design/support.js`.

## Critique

Method: impeccable critique, single context (this design ran as one agent), with the impeccable
detector on `src/`.

- The first images showed the `Join your team` heading and text at the top of both screens,
  left over from the invite artboard the styles were copied from. Fixed: each artboard has only
  its own page.
- The sign-in artboard keeps the starter's layout: the button and `Forgot password?` in one
  column, 12px apart. With `Create an account` gone, nothing else moves.
- The closed page puts its text and its link as separate parts of the frame, 24px apart, as
  `AuthPageFrame` lays out its children on every auth page. No change.
- Detector: no findings.

Result: passed

## Polish

- Every control is a real link, input, label or button with a name for screen readers: Email,
  Password, `Sign in`, `Forgot password?`, and the `Sign in` link on the closed page.
- The text on the closed page is the muted foreground on the page background, the same pair as
  the text on the invite page, and the links are underlined, so they do not depend on colour.
- Spacing, radius, borders, type sizes and colours are the starter's shadcn tokens, as on the
  FORGE-DEFAULTS-1 artboards. No new token.
- The column is at most 384px wide with 24px padding, so both screens fit a 390px phone without
  sideways scroll.
- Loading, error and empty states and their copy are in SCREENS.md for both screens.

Result: passed

## Emil checklist

- No new animation. The pages have no dialog, popover or toast.
- The button keeps the shadcn default, with no movement on hover.
- The closed page has no state change, so nothing on it can jump.

Result: passed
