import { expect, test } from '@playwright/test';

/** Phase 1 smoke: the shell renders, the IA is navigable, the API answers. */

test('about page states the demo and data-honesty position', async ({ page }) => {
  await page.goto('/about');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.getByRole('note')).toContainText('No real payments');
  await expect(page.getByText('labelled')).toBeVisible();
});

test('console entry point deep-links into the Streamlit console', async ({ page }) => {
  await page.goto('/console');
  await expect(
    page.getByRole('heading', { name: 'The conversion intelligence console' }),
  ).toBeVisible();

  const base = process.env.NEXT_PUBLIC_CONSOLE_URL ?? 'http://localhost:8501';
  await expect(page.getByRole('link', { name: /open the console/i })).toHaveAttribute('href', base);
  // Every section card links to its own Streamlit page.
  for (const [label, slug] of [
    ['Funnel', 'funnel'],
    ['Experiments', 'experiments'],
    ['Copilot', 'copilot'],
  ] as const) {
    await expect(page.getByRole('link', { name: label })).toHaveAttribute(
      'href',
      `${base}/${slug}`,
    );
  }
});

test('theme toggle switches and persists', async ({ page }) => {
  await page.goto('/');
  const html = page.locator('html');
  await expect(html).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('button', { name: /switch to light theme/i }).click();
  await expect(html).toHaveAttribute('data-theme', 'light');
  await page.reload();
  await expect(html).toHaveAttribute('data-theme', 'light');
});

test('skip link is the first focusable element', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
});

test('health endpoint reports wiring', async ({ request }) => {
  const response = await request.get('/api/health');
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  expect(body.llmProvider).toBe('mock');
  expect(body.phase).toBe(5);
});

test('event ingest validates and accepts a batch', async ({ request }) => {
  const bad = await request.post('/api/events', { data: { events: [], sent_at: 'nope' } });
  expect(bad.status()).toBe(400);

  const event = {
    event_id: crypto.randomUUID(),
    event_type: 'page_view',
    timestamp: new Date().toISOString(),
    user_id: 'e2e_user',
    session_id: 'e2e_session',
    device: 'desktop',
    traffic_source: 'direct',
    is_new_user: true,
    page: '/',
    experiment_assignments: {},
    properties: {},
  };
  const good = await request.post('/api/events', {
    data: { events: [event], sent_at: new Date().toISOString() },
  });
  expect(good.status()).toBe(202);
  expect((await good.json()).accepted).toBe(1);

  // Replaying the same beacon must not duplicate the row.
  const replay = await request.post('/api/events', {
    data: { events: [event], sent_at: new Date().toISOString() },
  });
  expect((await replay.json()).accepted).toBe(0);
});
