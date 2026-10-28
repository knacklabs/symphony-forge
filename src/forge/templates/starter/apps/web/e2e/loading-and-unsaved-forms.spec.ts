import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { signUp } from './helpers';

/** Holds the next answer for this API path until `release` is called, so the screen stays loading. */
function holdNext(page: Page, path: string) {
  let release: () => Promise<void> = async () => undefined;
  const held = new Promise<void>((resolve) => {
    void page.route((url) => url.pathname === path, async (route) => {
      const response = await route.fetch();
      release = () => route.fulfill({ response });
      resolve();
    }, { times: 1 });
  });
  return { held, release: () => release() };
}

test('the projects, members and change history lists show skeleton rows while they load', async ({ page }) => {
  await signUp(page);

  const projects = holdNext(page, '/api/v1/projects');
  await page.reload();
  await projects.held;
  const loadingProjects = page.getByRole('status', { name: 'Loading projects' });
  await expect(loadingProjects.locator('[data-slot="skeleton"]')).toHaveCount(3);
  await projects.release();
  await expect(page.getByText('No projects yet.')).toBeVisible();
  await expect(loadingProjects).toHaveCount(0);

  const members = holdNext(page, '/api/v1/members');
  await page.getByRole('link', { name: 'Members' }).click();
  await members.held;
  const loadingMembers = page.getByRole('status', { name: 'Loading members' });
  await expect(loadingMembers.locator('[data-slot="skeleton"]')).toHaveCount(3);
  await members.release();
  await expect(page.getByRole('table').first()).toBeVisible();
  await expect(loadingMembers).toHaveCount(0);

  const history = holdNext(page, '/api/v1/history');
  await page.getByRole('link', { name: 'Change history' }).click();
  await history.held;
  const loadingHistory = page.getByRole('status', { name: 'Loading change history' });
  await expect(loadingHistory.locator('[data-slot="skeleton"]')).toHaveCount(3);
  await history.release();
  await expect(page.getByText('No changes yet.')).toBeVisible();
  await expect(loadingHistory).toHaveCount(0);
});

test('the invite and add-agent forms ask before they close with unsaved text', async ({ page }) => {
  await signUp(page);
  await page.getByRole('link', { name: 'Members' }).click();

  const forms = [
    { opener: 'Invite person', field: 'Email', text: 'someone@example.com', question: 'Discard this invite?' },
    { opener: 'Add agent account', field: 'Name', text: 'gantry', question: 'Discard this agent account?' },
  ];
  for (const { opener, field, text, question } of forms) {
    const openButton = page.getByRole('button', { name: opener });
    const dialog = page.getByRole('dialog', { name: opener });
    const discard = page.getByRole('alertdialog', { name: question });

    // An empty form still closes at once.
    await openButton.click();
    await expect(dialog.getByLabel(field)).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(discard).toHaveCount(0);

    // A stray click outside asks first, and Keep editing keeps the typed text.
    await openButton.click();
    await dialog.getByLabel(field).fill(text);
    await page.mouse.click(5, 5);
    await expect(discard).toBeVisible();
    await expect(discard.getByRole('button', { name: 'Keep editing' })).toBeFocused();
    // Axe reads colours once the question's entry animation has finished.
    await discard.evaluate((element) => Promise.all(element.getAnimations({ subtree: true }).map((animation) => animation.finished)));
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);
    await discard.getByRole('button', { name: 'Keep editing' }).click();
    await expect(dialog.getByLabel(field)).toHaveValue(text);

    // Esc asks too; Discard closes the form, gives the focus back to its opener and clears the text.
    await page.keyboard.press('Escape');
    await expect(discard).toBeVisible();
    await discard.getByRole('button', { name: 'Discard' }).click();
    await expect(dialog).toBeHidden();
    await expect(openButton).toBeFocused();
    await openButton.click();
    await expect(dialog.getByLabel(field)).toHaveValue('');
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
  }
});
