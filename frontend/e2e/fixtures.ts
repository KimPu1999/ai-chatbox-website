import { test as base } from '@playwright/test';

// Browser tests use an explicit unauthenticated API fixture. This keeps the
// smoke suite independent of a developer database; production API behavior is
// covered by HTTPX/integration tests and the CI job provisions PostgreSQL.
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'unauthenticated' }) }),
    );
    await page.route('**/api/v1/platform/auth/me', (route) =>
      route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'unauthenticated' }) }),
    );
    await use(page);
  },
});

export { expect } from '@playwright/test';
