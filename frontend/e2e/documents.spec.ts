import { expect, test } from './fixtures';

test('document library is protected', async ({ page }) => {
  await page.goto('/documents');
  await expect(page).toHaveURL(/\/login\?next=%2Fdocuments/);
});
