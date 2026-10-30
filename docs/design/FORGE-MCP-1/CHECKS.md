# Design checks

The checks ran on the four artboards in `src/` and their 1440 by 900 images. The fixes went into
the artboards in one pass, and the images were made again with `.forge/design/support.js`.

## Critique

Method: impeccable critique, single context (this design ran as one agent), with the impeccable
detector on `src/`.

- The agent rows had an `Agent` Badge after the email, inside a section already headed
  `Agent accounts`. Fixed: the Badge is gone.
- Agent accounts are in their own section under the people table, so the people table and its
  Invite flow do not change, and the key buttons sit only on agent rows.
- The Agent access dialog shows the four tools that are always on as plain rows, so the one
  Switch reads as the only choice.
- Detector, not changed: "cramped padding" on the table wrappers. The table cells have the
  shadcn 8px padding, as on the FORGE-FEATURE-1 artboards, so these are false positives.

Result: passed

## Polish

- Every control is a real button, input or label with a name for screen readers: each Role
  Select names its email, Create key and Revoke key name the email, the key field has the label
  `Key`, and the dialogs have a Close button.
- The Switch has `role="switch"`, `aria-checked` and a visible label; the key warning is a
  status region.
- Revoke key uses the destructive text colour with 4.5 to 1 contrast or more; the help text
  uses the muted colour, as on the starter's other forms.
- Spacing, radius, borders, type sizes and colours are the starter's shadcn tokens, as on the
  FORGE-FEATURE-1 artboards. No new token. The key field uses the system monospace font.
- Loading, empty, error and failure states and their copy are in SCREENS.md for every screen.

Result: passed

## Emil checklist

- No new animation. The Dialog, AlertDialog, Select, Switch and toast use the shadcn and Sonner
  defaults, which animate only transform and opacity and stay under 300ms.
- The dialogs stay centred; the Select lists open from their trigger, as Radix sets them.
- Copy confirms with a toast and does not move the layout.
- A key change updates the Key Badge with no animation.

Result: passed
