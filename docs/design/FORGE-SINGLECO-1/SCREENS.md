# Screens for an app set to one company

Structure only. Both screens use the starter's neutral shadcn/ui theme and its existing auth page
frame (`AuthPageFrame`: a centred column 384px wide, the heading above, 24px between parts). No
new look, colour or font.

## Sign in

Image: sign-in.png
Route: `/sign-in`, in the auth page frame. Anyone can open it.
Components: AuthPageFrame, Form, Input, Button
Fields:
- Email: email, required
- Password: password, required

This is today's sign-in page with one change: the line `New here? Create an account` is gone.
Everything else stays as it is now.

- Heading `Sign in`.
- Button `Sign in` (primary, full width; `Signing in…` while it waits), and under it the link
  `Forgot password?`.
- Validation messages show under the field, as now.
- Error: `Could not sign in. Check your email and password, then try again.` above the button.
- A person with an invite joins from the invite link, which opens the existing `Join your team`
  page. This page does not point to it.

## Sign-up closed

Image: sign-up-closed.png
Route: `/sign-up`, in the auth page frame. Anyone can open it. The page replaces the sign-up
form on this route.
Components: AuthPageFrame
Fields: none

- Heading `Sign-up is closed`.
- Text `This app is for one company. Ask an admin of your team for an invite.` (muted).
- Link `Sign in`, to `/sign-in`. It is the only control on the page and the keyboard target.
- No form, so no loading, error or empty state. The page shows the same content every time.

## An app for many companies

An app set to many companies keeps today's sign-in and sign-up pages unchanged: the sign-in page
keeps `New here? Create an account`, and `/sign-up` keeps the `Create account` form. No image is
needed.
