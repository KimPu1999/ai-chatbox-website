import { expect, test } from './fixtures';

test('conversation URLs do not bypass authentication', async ({ page }) => {
  await page.goto('/chat/conversation-for-test');
  await expect(page).toHaveURL(/\/login\?next=%2Fchat%2Fconversation-for-test/);
});
