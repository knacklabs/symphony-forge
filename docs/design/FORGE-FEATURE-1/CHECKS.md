# Design checks

The checks ran on the six artboards in `src/` and their 1440 by 900 images. The fixes went into
the artboards in one pass, and the images were made again with `.forge/design/support.js`.

## Critique

Method: impeccable critique, single context (this design ran as one agent), with the impeccable
detector on `src/`.

- The detail screen repeated the client under the heading and in the Details card. Fixed: the
  line under the heading is gone.
- The billable filter said `Billable: any`, unlike `All statuses` and `All clients`. Fixed: it
  says `Billable or not`.
- The form showed an error on Client, but Client is optional. Fixed: only Name is required, and
  the errors shown are for Name, Hours budget, Due date and Contact email.
- One Recent changes entry did not say what the value became. Fixed: every entry names the old
  and the new value.
- Detector: the `USD` text in front of the Budget field had 4.3 to 1 contrast on its grey fill.
  Fixed: the fill is gone, so the text is on the page background, as in shadcn's input group.
- Detector, not changed: "cramped padding" on the table wrapper and on the Recent changes list.
  The table cells have the shadcn 8px padding and the list items have 12px between them and the
  divider, so these are false positives.

- Restore (second pass, on the two new artboards and the changed list): the Switch sits at the
  end of the filter row, so the row still reads as filters. Deleted rows keep 4.5 to 1 contrast
  with the muted text. The deleted detail screen hides Edit and Delete, so Restore is its only
  action. The detector found only the same two false positives.

Result: passed

## Polish

- Every control is a real button, link, input or label with a name for screen readers: the
  search box, each filter Select, the sort buttons, the row links, Edit, Delete, the dialog Close
  button and the form fields.
- The first-page Previous button is off, and the sorted column has `aria-sort`.
- Numbers, money, dates and times use tabular figures; Budget is right-aligned in the table.
- Spacing, radius, borders, type sizes and colours are the starter's shadcn tokens, as on the
  FORGE-DEFAULTS-1 artboards. No new token.
- The Show deleted Switch has `role="switch"`, `aria-checked` and a visible label; the deleted
  detail Alert is a status region and names who deleted the project and when.
- Loading, empty, no-results, error and not-found states and their copy are in SCREENS.md for
  every screen.

Result: passed

## Emil checklist

- No new animation. The Dialog, AlertDialog, Select, Combobox and toast use the shadcn and
  Sonner defaults, which animate only transform and opacity and stay under 300ms.
- The Ctrl+K list and the sort buttons have no animation, because people use them many times a
  day from the keyboard.
- The row hover is a background colour only, with no movement.
- The dialogs stay centred; the Select and Combobox lists open from their trigger, as Radix sets
  them.
- The Switch moves its thumb with the shadcn default; the restore Alert and Badge leave with no
  animation, and the toast confirms the restore.
- A page change keeps the old rows until the new rows arrive, so the table does not jump.

Result: passed
