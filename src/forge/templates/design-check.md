# Canvas completeness check

Check the signed canvas against the app's brief. This is a design check, not a code review.
Read `docs/design/prototype/SCREENS.md` and every screen image it names in this checkout.
Compare the screens with the brief's Summary, Users, Things it keeps track of and Key flows below.
Every thing, field and choice-list option in Things it keeps track of must appear on a screen.
Report each key flow that no screen in SCREENS.md carries.
Report a missing screen, field, option, flow or other checklist gap as P0 or P1.
Give the file, line and concrete evidence for each gap. Do not infer completeness from a passed
skill result. Apply each checklist item to the app's stated scope and explain an explicit exception.
Use the strict review report format with review_status and findings, including an empty findings
list when the whole check passes. This check must finish before sign-off.

## Entities and fields

- Show each entity from the interview in a list, detail screen, create form and edit form.
- Show each field in detail and in the form, or state why it is computed, hidden or a system field.
- Give each field a label, type, required or optional state, sample value and validation rule.
  Add help text where its meaning is unclear.
- Choose list columns on purpose. Make other fields reachable through detail or column visibility.
- Mark read-only and system fields, such as id, created by, created at and updated at.
- Link lists and details to related entities. Let forms select related records.
- Give every row-level object an extended detail screen, with tabs for related data, activity and files.

## Dropdowns and choice lists

- Show every option for each Select, Combobox, radio group and filter.
- State whether each list is fixed or user-editable. Give its default and empty-list behavior.
  State whether search is needed for a list with more than about ten options.
- List allowed status transitions and the roles that can make each change.

## States per screen

- Show empty states for first use and filtered results, loading skeletons, errors with retry,
  success toasts and partial or slow results.
- Show permission denied for each role. Explain hidden or disabled controls.
- Show offline and expired-session states.
- Show that long text, long names and large numbers fit the layout.
- Show pagination or scroll for many rows, with zero, one and many examples.

## Navigation

- Make each screen reachable from a sidebar, link, command palette or row click. No screen is orphaned.
- Give each screen a way back: breadcrumb, back or cancel.
- State the destination after create, edit and delete.
- Show the sidebar collapsed, expanded and as a mobile sheet.
- Show deep links and a 404 state for unknown ids.

## Forms and validation

- Give each required field a plain error message. Show at least one invalid submit per form.
- Show server errors, such as duplicates and conflicts.
- Define cancel and unsaved-change behavior.
- Show progress and a way back in multi-step forms.

## Destructive and risky actions

- Use an AlertDialog for delete, archive, revoke and bulk actions. Name the item and the effect.
- State an undo or restore path, such as soft delete or a trash view.
- Show the selected count and a clear way to cancel bulk selection.
- Show each action only to permitted roles.

## Cross-cutting

- Show light and dark themes for at least the shell and one form.
- Show phone, tablet and desktop widths for the shell, a table and a form.
- Show the keyboard path: tab order, Cmd+K, Cmd+B and Esc to close dialogs.
- Use only shadcn/ui components. List each custom piece and its reason.
- Include notification, settings, profile and sign-in screens.
- Check the copy: no jargon, and verbs on buttons, such as "Save client".
- Confirm that the sign-off record states the owner's entities, dropdown lists and screen list in plain words.
