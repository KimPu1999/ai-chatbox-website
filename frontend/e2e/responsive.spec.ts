import { expect, test } from './fixtures';

test('authentication page fits a mobile viewport without horizontal overflow', async ({ page }) => {
  await page.goto('/login');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
});
