# Orders for a bread wholesaler

A small wholesaler sells bread to local shops. It needs one app for its staff to manage orders.
This is a made-up business. It names no real company.

## Who uses it

Only the wholesaler's staff. A staff member is ready when the app starts: the email is
`staff@example.test` and the password is `bread-and-butter-1`.

## What staff do

- **Sign in.** Staff sign in with an email and a password. After they sign in they see an
  "Orders" link and a "Dashboard" link.
- **See a list of orders.** The "Orders" page has the heading "Orders" and a table of orders.
  Each order shows the shop, the item, the quantity, the delivery date and its status.
- **Add an order with a form.** On the "Orders" page, a "New order" button opens a form with the
  fields "Shop", "Item", "Quantity" and "Delivery date" and a "Save" button. After "Save", the
  new order is in the list. A new order is "Open".
- **See a dashboard.** The "Dashboard" page shows "Orders due today" and "Late orders". Each one
  is a section named by its label (a `<section>` with `aria-label` or `aria-labelledby`) and has a
  number inside it.

## Calls for the wholesaler's other systems

Both calls are made as a signed-in staff member, with the same session and `x-csrf-token` header
that the app's own pages use. Each answers with a success status when it has done its work.

- **Add an order.** `POST /api/orders` with a JSON body of `shop`, `item`, `quantity` (a whole
  number) and `deliveryDate` (like `2020-01-31`). The date can be in the past, because the
  wholesaler's other systems send orders late. The new order is "Open".
- **The nightly job.** The wholesaler runs its own scheduler. Each night it calls the app at one
  address: `POST /api/jobs/mark-late-orders`. The job marks every open order whose delivery date
  has passed as "Late". The app does not schedule anything.
