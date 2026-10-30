# Screens for agent accounts and agent access

Structure only. Every screen uses the starter's neutral shadcn/ui theme and its existing app shell
(sidebar, header, user menu). No new look, colour or font. Dates use `YYYY-MM-DD` from
`formatDate` in `@app/shared`.

These screens add agent accounts to the Members screen and an Agent access dialog to each
feature's list screen. The example feature is projects. The feature command copies the Agent
access button and dialog for every new feature, and `projects` becomes the feature's plural.

## Members with agent accounts

Image: members-agents.png
Route: `/members`, inside the app shell. Admins and members can open it.
Components: Table, Badge, Select, Button, AlertDialog (Revoke key), sonner toast
Fields:
- Role (one per agent row): choice, required, options: Admin | Member

- The people table stays as it is, with heading `Members`, text `People in your organisation.`,
  `Export CSV` and `Invite person`. Agent accounts are not in the people table.
- Under it, a section with the heading `Agent accounts` and the text
  `Agents use this app's tools with their own role and key.` Admins see `Add agent account`
  (outline) on the right of the heading. It opens the Add agent account dialog.
- Columns: Email, Role, Key, and the row buttons (the column has the screen-reader name
  `Actions`). Email is the agent account's email, such as `gantry-k3x9p2@agents.invalid`.
  Role is a Select for admins, with the label `Role for <email>`, as on the people rows; a role
  change has the toast `Role updated.`
- Key: a Badge, `Key active` (outline) when the account has a key, `No key` (secondary) when it
  has none.
- Row buttons, admins only (outline, small): `Create key` on every agent row, and `Revoke key`
  (destructive text) on a row with a key. Each button's screen-reader name names the email.
- Create key opens the Agent key dialog. On a row with a key, the new key replaces the old one,
  and the old one stops working at once.
- Revoke key opens an AlertDialog: title `Revoke this key?`, text `Agents that use it stop
  working at once.`, buttons `Cancel` (outline, has the focus when it opens) and `Revoke key`
  (destructive; `Revoking…` while it waits). Success: the toast is `Key revoked.` and the row
  shows `No key`. Failure: the dialog stays open and the toast is
  `Could not revoke the key. Try again.`
- Members see the agent rows with the role as a Badge and no buttons.
- Loading: `Loading members…` (status), for both tables, as now.
- Empty: `No agent accounts yet.` and, for admins, `Add one so an agent can use this app's
  tools.` The section heading and `Add agent account` stay.
- Error: `Could not load members. Check your connection and try again.` with `Try again`, as now.
- On a phone the heading and the button stack, and the table scrolls sideways.

## Add agent account

Image: agent-add.png
Opens from `Add agent account` on the Members screen. Admins only.
Components: Dialog, Form, Input, Select, Button, sonner toast
Fields:
- Name: text, required
- Role: choice, required, options: Member | Admin

- Title `Add agent account`, text `An agent uses this app's tools with this role. You create its
  key next.`
- Name has the help text `Lower-case letters, numbers and hyphens, such as gantry.` Role starts
  on Member.
- Buttons: `Cancel` (outline) and `Add agent account` (primary; `Adding…` while it waits).
- Validation, under the field, after the first submit and then while the person types:
  - Name empty: `Enter a name.`
  - Name not valid: `Use 2 to 40 lower-case letters, numbers or hyphens, starting with a letter.`
  The focus moves to Name.
- An API error with no field: `Could not add the agent account. Try again.` above the buttons.
- Success: the dialog closes, the row shows in Agent accounts with `No key`, and the toast is
  `Agent account added.`

## Agent key

Image: agent-key.png
Opens from `Create key` on an agent row. Admins only.
Components: Dialog, Input (read-only), Button, Alert, sonner toast
Fields:
- Key: text, required (read-only)

- Title `Agent key`, text `The key for <email>. Give it to the agent's connection.`
- The key is in a read-only field with the label `Key`, in a monospace font, and `Copy`
  (outline) beside it. Copy puts the key on the clipboard and the toast is `Key copied.` If the
  copy fails, the toast is `Could not copy. Select the key and copy it.`
- An Alert (status) under it: `Copy this key now. You cannot see it again.`
- Button: `Done` (primary). Done, Close and Escape close the dialog, drop the key from the page,
  and the row shows `Key active`.
- While the key is made, the dialog shows `Creating key…` (status). Failure: the dialog shows
  `Could not create a key. Try again.` with `Try again`, and the row keeps its old key.

## Agent access

Image: agent-access.png
Opens from `Agent access` (outline) beside `Export CSV` on each feature's list screen. Admins
only: a member never sees the button.
Components: Dialog, Switch, Button, sonner toast
Fields:
- Agents can delete and restore projects: yes or no, optional

- Title `Agent access`, text `Choose which project tools agents can use.`
- A list of the tools: `Search projects`, `View a project`, `Create projects` and `Edit projects`,
  each with a check and `Always on`. The last row is a Switch, `Agents can delete and restore
  projects`, off by default.
- Under the list: `The agent account's role still applies. A Member agent cannot delete or
  restore.`
- A Switch change saves at once and the toast is `Agent access updated.` Failure: the Switch
  goes back and the toast is `Could not update agent access. Try again.`
- Loading: `Loading agent access…` (status) in place of the list; the Switch is off while it
  waits.
- Button: `Done` (primary) closes the dialog.
