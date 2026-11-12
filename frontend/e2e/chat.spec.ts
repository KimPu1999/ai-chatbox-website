import { expect, test } from './fixtures';

test('anonymous chat access is denied by the protected route', async ({ page }) => {
  await page.goto('/chat');
  await expect(page).toHaveURL(/\/login\?next=%2Fchat/);
});
