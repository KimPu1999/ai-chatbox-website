import { expect, test } from './fixtures';

test('login page exposes accessible authentication controls', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: /sign in|log in/i })).toBeVisible();
  await expect(page.getByLabel(/email/i)).toBeVisible();
  await expect(page.getByLabel(/password/i)).toBeVisible();
});

test('platform login is a separate entry point', async ({ page }) => {
  await page.goto('/platform/login');
  await expect(page.getByText(/platform control center/i)).toBeVisible();
  await expect(page.getByLabel(/email/i)).toBeVisible();
});
