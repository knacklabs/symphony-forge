# Screens for the /forge pane

The pane shows what runs now on this laptop. Claude Code draws it with its own parts, so the
terminal's font and colours are the terminal's. The Claude desktop app lets a pane use text sizes
and weights, box colours and borders, primary and secondary buttons and small drawings, so the
desktop app gets a richer drawing. Both use the same words and the same order.

The owner saw these screens on the design canvas on 13 Nov 2026 and said yes to them.
Canvas: https://claude.ai/artifact/7dvfmg2ebmh1Eds17U7UkX
The pages in `src/` are copies of the canvas artboards. The images were made from them.

## Claude desktop app

### Work is running

Image: desktop-running.png (440 by 1000)

- Header: "Forge" and "this laptop".
- Two meters: "Builds and reviews" and "Tests", each with the places in use, as "3 of 4" and a
  bar of four parts.
- One line: "Nothing needs you."
- Headings BUILDING, TESTS, REVIEW. A heading with no runs does not show.
- Each run is a card: a filled dot, the title, the time on the right. Below: the round and the
  model as two small tags, and the current step in code type when Forge knows it.
- A run from another repo adds "in <repo name>" after its title, in lighter text.
- A test run shows its round as a tag, a progress bar and "212 of 640 tests".
- The selected card has a dark border. It shows "LATEST OUTPUT" with the last three lines of the
  run's output, and the buttons "Open output" (primary) and "Stop run" (secondary).

### Something needs you, runs wait

Image: desktop-needs-you.png (440 by 1000)

- A soft banner in place of the plain line: "2 items need you" and
  "First: Show late orders has a question for you."
- A waiting run has a hollow dot, its round as a tag, and the line "Waiting for its tests" or
  "Waiting for a free place".
- Last line when the machine is busy: "The machine is busy. New runs wait."

### Forge did not answer

Image: desktop-forge-did-not-answer.png (440 by 380)

- The last cards stay. A quiet box at the bottom says
  "Last update 2 min ago. Forge did not answer."

## Terminal

Text, boxes and buttons only. No drawings, no meters, no tags, no output lines.

### Wide terminal

Images: pane-running.png, pane-needs-you.png, pane-nothing-running.png,
pane-forge-did-not-answer.png (460 wide)

- Each run is two lines: the title, then "Round 3 · 21 min · editing land.py". A waiting run
  and a test run keep their round: "Round 1 · Waiting for a free place · 2 min" and
  "Round 2 · 212 of 640 tests · 3 min".
- The selected run has a filled background.
- "Nothing is running." when no run exists.
- The buttons "Open output" and "Stop run" sit at the bottom.

### Narrow terminal

Image: pane-narrow-terminal.png (1000 by 250)

- A frame above the prompt. One line for each run:
  "Building  One combined check for ready changes · round 3 · 21 min · editing land.py".

### Text reply

Image: pane-text-reply.png (1000 by 300)

- Where no pane can be drawn, /forge answers with the same lines as text.
