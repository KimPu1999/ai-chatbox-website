import { expect, test } from './fixtures';

test('platform control center does not expose data before admin MFA', async ({ page }) => {
  await page.goto('/platform/overview');
  await expect(page).toHaveURL(/\/platform\/login/);
});
