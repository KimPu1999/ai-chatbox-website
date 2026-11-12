import { expect, test } from './fixtures';

test('ordinary user entry points cannot reach platform routes anonymously', async ({ page }) => {
  await page.goto('/platform/users');
  await expect(page).toHaveURL(/\/platform\/login/);
});
