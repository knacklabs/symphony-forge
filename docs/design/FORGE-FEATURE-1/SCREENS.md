# Screens for a feature from the starter

Structure only. Every screen uses the starter's neutral shadcn/ui theme and its existing app shell
(sidebar, header, user menu). No new look, colour or font. Dates use `YYYY-MM-DD` and times use
24-hour `HH:mm`, in the person's time zone, from `formatDate` and `formatDateTime` in
`@app/shared`. Money shows as `formatMoney` gives it, for example `USD 48,000.00`.

These are the projects screens. `forge task feature` copies them for every new feature, so each
screen names the parts that the command fills from the feature's fields as **Filled:**. All
other text changes only by name: `Projects` becomes the feature's plural and `project` its
singular. In the HTML, each filled element has a `data-fill` attribute.

The example feature has these fields, one of each kind: Name (text), Description (long text),
Hours budget (number), Budget (money), Due date (date), Billable (yes or no), Contact email
(email), Status (status list: Planned | Active | Done) and Client (a link to one client).

## Projects

Image: projects-list.png
Route: `/projects?search=<text>&status=<status>&client=<id>&billable=<yes|no>&deleted=<yes>&sortBy=<column>&sortOrder=<asc|desc>&after=<cursor>`,
inside the app shell. Admins and members can open it.
Components: Input, Select, Switch, Table, Badge, Button
Fields:
- Search: text, optional
- Status filter: choice, optional, options: All statuses | Planned | Active | Done
- Client filter: choice, optional, options: All clients | each client by name
- Billable filter: choice, optional, options: Billable or not | Billable | Not billable
- Show deleted: yes or no, optional (admins only)

Filled: the search box (on the first text or email field, with the placeholder
`Search by <field>`; a feature with no such field has no search box), one Select per yes-or-no,
status-list and link field, and the table columns.

- Heading `Projects`, text `Create and manage your projects.`
- Buttons next to the heading: `Export CSV` (outline) and `New project` (primary, opens the form).
- Columns: Name, Status (Badge, outline), Client, Due date, Budget (right-aligned), Updated. Each
  column header is a sort button with the sort arrow, as now. Default sort: Updated, newest first.
- The search, each filter, the sort and the page are kept in the web address. A reloaded or
  shared link shows the same list. A change to the search, a filter or the sort goes back to the
  first page.
- The search waits until the person stops typing, then updates the list. The search box has the
  label `Search projects` for screen readers.
- Show deleted: a Switch with the label `Show deleted` at the end of the filter row, off by
  default and kept in the web address as the filters are. Admins only: a member never sees the
  Switch, and the API ignores the key for a member. When it is on, the list shows the deleted
  projects among the others. A deleted row has a `Deleted` Badge (secondary) after its name and
  muted text, and it still opens the detail screen. The total under the table says `About 1,300
  projects, deleted ones included`. The image `projects-deleted.png` shows the Switch on.
  Export CSV exports what the list shows, so it includes deleted projects only when the Switch
  is on.
- Each row opens the detail screen: the name is a link and the whole row can be clicked. The
  name link is the keyboard target.
- Under the table: `About 1,200 projects` (the approximate total, rounded) on the left, and
  `Previous` and `Next` (outline, small) on the right. Previous is off on the first page; Next is
  off on the last page. Below 100 items the total is exact: `24 projects`, `1 project`.
- Loading: `Loading projects…` (status). A page change keeps the old rows on screen until the
  new rows arrive.
- Empty, with no search and no filter: `No projects yet.` and `Create a project to keep its
  status in one place.`
- No results for a search or a filter: `No projects match this search.` and `Try other words or
  clear the filters.` with a `Clear search and filters` button (outline).
- Error: `Could not load projects. Check your connection and try again.` with a `Try again`
  button.
- The table scrolls sideways on a phone; the search box and the Selects wrap to their own lines.

## Project detail

Image: project-detail.png
Route: `/projects/:id`, inside the app shell. The breadcrumb is `Projects › <name>`, and
`Projects` goes back to the list with its last search and filters.
Components: Breadcrumb, Badge, Button, Card, AlertDialog (opens Delete project), sonner toast
Fields:
- Name: text, required
- Status: choice, required, options: Planned | Active | Done
- Client: link, optional
- Due date: date, optional
- Hours budget: number, optional
- Budget: money, optional
- Billable: yes or no, required
- Contact email: email, optional
- Description: long text, optional
- Created: date and time, required
- Last changed: date and time, required

All fields are read-only on this screen.

Filled: the heading (the first text field), the status Badge (the first status-list field), and
one row in the Details card per field. Created and Last changed come from the audit columns and
are on every feature.

- Heading: the project name, with its status Badge.
- Buttons next to the heading: `Edit` (outline, opens the form with the project's values) and
  `Delete` (outline, destructive text). An admin sees both. A member sees only `Edit`.
- Details card: each field with its label above its value. A link field shows the linked item's
  name as a link to its detail screen. An email shows as a mail link. A yes-or-no field shows
  `Yes` or `No`. An empty field shows `None`. Long text wraps across the full card width.
- Under the fields: `Created` `2026-10-02 09:14 by ada@example.com` and `Last changed`
  `2026-10-24 16:42 by grace@example.com`.
- Recent changes card: heading `Recent changes`, text `The last 5 changes to this project.` Each
  entry has what changed, for example `Status changed from Planned to Active`, and below it who
  and when: `grace@example.com · 2026-10-24 16:42`. The last entry is `Created the project`.
  Under the list, for admins only, the link `Open the change history` goes to `/history`.
  A member sees the list without the link.
- Toasts: after a save in the form, `Project updated.`
- Loading: `Loading project…` (status). Error: `Could not load this project. Check your
  connection and try again.` with a `Try again` button. A project that does not exist or was
  deleted: `This project does not exist or was deleted.` with a `Back to projects` link.
- Recent changes, while it loads: `Loading changes…` (status). If it fails: `Could not load the
  recent changes.` with a `Try again` button; the Details card still shows.
- On a phone the two cards stack, Details first.

## Projects with deleted ones

Image: projects-deleted.png
Route: `/projects?deleted=yes`, the Projects screen with `Show deleted` on. Admins only.
Components: Switch, Table, Badge (the Projects screen's parts)
Fields: as on Projects.

- Deleted rows: a `Deleted` Badge (secondary) after the name, muted text in every cell.
- Empty, with the Switch on and nothing at all: `No projects yet.` as on Projects.
- No results: `No projects match this search.` as on Projects; `Clear search and filters` also
  turns the Switch off.

## Deleted project

Image: project-deleted.png
Route: `/projects/:id` for a deleted project. Admins only.
Components: Breadcrumb, Badge, Alert, Button, Card, sonner toast
Fields: as on Project detail, all read-only.

- Heading: the project name, its status Badge and a `Deleted` Badge (secondary).
- Under the heading, an Alert: `This project was deleted on 2026-10-25 by grace@example.com.`
  (the date from `formatDate`, the person who deleted it) with a `Restore` button (outline,
  small; `Restoring…` while it waits).
- `Edit` and `Delete` are hidden.
- Recent changes lists the delete first: `Deleted the project`, `grace@example.com ·
  2026-10-25 10:02`.
- After restore: the toast is `Project restored.`, the Alert and the `Deleted` Badge go, `Edit`
  and `Delete` come back, and Recent changes lists `Restored the project` above `Deleted the
  project`. Last changed shows the restore.
- Restore fails: the toast is `Could not restore this project. Try again.` and the screen stays.
- A member who opens a deleted project's address sees `This project does not exist or was
  deleted.` with a `Back to projects` link, as for any missing project.

## Delete project

Image: project-delete.png
Opens from `Delete` on the Project detail screen. Admins only.
Components: AlertDialog, Button
Fields: none

- Title `Delete project?`, text `The project “<name>” will be deleted. You cannot undo this.`
- Buttons: `Cancel` (outline, has the focus when the dialog opens) and `Delete project`
  (destructive; `Deleting…` while it waits).
- Success: the dialog closes, the list opens, and the toast is `Project deleted.` An admin can
  restore it from the Deleted project screen.
- Failure: the dialog stays open and the toast is `Could not delete this project. Try again.`

## Project form

Image: project-form.png
Opens from `New project` on the Projects screen and from `Edit` on the Project detail screen.
The starter's form is a Dialog, so this is a Dialog too.
Components: Dialog, Form, Input, Textarea, Select, Combobox (Popover with Command, for the link
field), Checkbox, Button, AlertDialog (Discard changes), sonner toast
Fields:
- Name: text, required
- Description: long text, optional
- Status: choice, required, options: Planned | Active | Done
- Client: link, optional
- Hours budget: number, optional
- Budget: money, optional
- Due date: date, optional
- Contact email: email, optional
- Billable: yes or no, optional

Filled: one form field per feature field, in the order of the feature's line, with the control
for its kind: text and email an Input, long text a Textarea, number an Input with a numeric
keyboard, money an Input with the currency (`USD`, from `formatMoney`) in front, date an Input
with the placeholder `YYYY-MM-DD`, yes or no a Checkbox, a status list a Select (its first option
is the default), and a link a Combobox that searches the other feature's items by name. Short
fields go two to a row; text and long text use the full width.

- Title `New project`, text `Add a project to your list.` For an edit: title `Edit project`,
  text `Change the project's details.`
- Buttons: `Cancel` (outline) and `Create project` (primary). For an edit: `Save changes`. While
  it waits: `Saving…`.
- Validation messages, under the field, shown after the first submit and then while the person
  types:
  - Name empty: `Enter a name.` Name too long: `Use 200 characters or fewer.`
  - Hours budget, when it is not a number: `Enter a number.`
  - Budget: `Enter an amount, such as 1,250.00.`
  - Due date: `Enter a real date as YYYY-MM-DD.`
  - Contact email: `Enter a valid email address.`
  - Client, when the linked client was deleted: `That client no longer exists. Choose another.`
  On submit with errors, the focus moves to the first field with an error.
- Client Combobox: placeholder `Search clients…`, while it loads `Loading clients…`, with no
  match `No clients found.`
- An API error with no field: `Could not save this project. Check the details and try again.`
  above the buttons.
- Toasts: `Project created.` after a create (the detail screen of the new project opens),
  `Project updated.` after an edit.
- Closing with unsaved changes asks first: title `Discard project changes?`, text `Your unsaved
  project changes will be lost.`, buttons `Keep editing` and `Discard changes`.
- On a phone the fields stack one to a row and the dialog scrolls.
