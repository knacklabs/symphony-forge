# Screens for the built-in defaults

Structure only. Every screen uses the starter's neutral shadcn/ui theme and its existing app shell
(sidebar, header, user menu). No new look, colour or font. Dates use `YYYY-MM-DD` and times use
24-hour `HH:mm`, in the person's time zone, from the helpers in `@app/shared`.

Navigation: the sidebar's Workspace group and the Ctrl+K list become Projects, Members, Change
history (admins only) and Settings. Each new screen has a header title and the shell's way back
through the sidebar.

## Members

Image: members.png
Route: `/members`, inside the app shell. Any member can open it.
Components: Table, Badge, Select, Button, Dialog (opens Invite person)
Fields:
- Email: email, required
- Role: choice, required, options: Admin | Member
- Joined: date, required

All three fields are read-only, except Role in the admin's view.

- Heading `Members`, text `People in your organisation.`
- Admin's view: an `Invite person` button and an `Export CSV` button (outline) next to the
  heading. The Role cell of each other person is a Select (Admin, Member). On a change the toast
  is `Role updated.`; on a failure it is `Could not change the role. Try again.` The admin's own
  row shows a Badge with the role and the text `You`, with no Select.
- Member's view: the same table with a Badge in each Role cell, the `Export CSV` button, and no
  `Invite person` button.
- Loading: `Loading members…` (status). Error: `Could not load members. Check your connection and
  try again.` with a `Try again` button. The list is never empty: it always has the person who
  opens it.
- Long emails wrap in the cell; the table scrolls sideways on a phone, as the projects table does.

## Invite person

Image: invite-dialog.png
Opens from `Invite person` on the Members screen. Admins only.
Components: Dialog, Form, Input, Button
Fields:
- Email: email, required

- Title `Invite person`, text `We will email them a link to join your organisation. The link
  works for 7 days.`
- Buttons: `Send invite` (primary; `Sending…` while it waits) and `Cancel`.
- Errors: a bad email shows the form's field message; `That person already has an account.`;
  `Email is not set up for this app yet.`; any other failure `Could not send the invite. Try
  again.`
- Success: the dialog closes and the toast is `Invite sent to <email>.`

## Join your team

Image: accept-invite.png
Route: `/accept-invite?token=<token>`, public, in the same page frame as Create account.
Components: Form, Input, Button
Fields:
- Email: email, required
- Password: password, required

- Title `Join your team`, text `Use the email address that got the invite.`
- Button `Join` (`Joining…` while it waits). Success opens Projects.
- A link with no token shows `This invite link is not complete. Ask an admin for a new one.` and
  no form.
- Errors: `This invite link is not valid. Ask an admin for a new one.`; `An account already uses
  that email, so it cannot join this organisation.`; field messages for the email and the
  password (12 to 128 characters), as on Create account.
- A link under the form: `Already have an account? Sign in`.

## Change history

Image: change-history.png
Route: `/history`, inside the app shell. Admins only.
Components: Table, Button
Fields:
- When: date and time, required
- Who: email, required
- What: text, required

All three fields are read-only.

- Heading `Change history`, text `Who changed what in your organisation.`, and an `Export CSV`
  button (outline).
- Rows: the newest 100 changes, newest first, for example `2026-10-24 14:05`, `ada@example.com`,
  `Invited grace@example.com`. The export has every change.
- Empty: `No changes yet.` Loading: `Loading change history…` (status). Error: `Could not load the
  change history. Check your connection and try again.` with a `Try again` button.
- A member who opens the address sees `Only an admin can see the change history.` and no table.

## Projects (changed)

Image: projects.png
Route: `/projects`. An existing screen with two changes.
Components: Table, Badge, Button (the existing parts, and one more Button)
Fields:
- Created: date, required
- Updated: date, required

- An `Export CSV` button (outline) next to `Create project`.
- The Created and Updated cells show `YYYY-MM-DD` from the shared helper, and lose the `by you`
  line.
