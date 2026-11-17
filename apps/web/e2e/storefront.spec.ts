import { expect, test } from '@playwright/test';
import { EventRecorder, addFirstProductToCart, fillShipping } from './helpers';

test.describe('storefront', () => {
  test('home page shows the catalog and states it is a demo', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toContainText(/giftware/i);
    await expect(page.getByRole('note')).toContainText('No real payments');

    // Categories come from the loaded catalog, not a hard-coded list.
    const categories = page.getByRole('navigation', { name: 'Categories' }).getByRole('link');
    expect(await categories.count()).toBeGreaterThan(3);

    await expect(page.getByRole('heading', { name: 'Best selling' })).toBeVisible();
    expect(await page.getByTestId('price').count()).toBeGreaterThan(0);
  });

  test('search narrows the catalog and keeps the query', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('searchbox', { name: 'Search products' }).fill('christmas');
    await page.getByRole('searchbox', { name: 'Search products' }).press('Enter');

    await expect(page).toHaveURL(/\/search\?q=christmas/);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('christmas');
    await expect(page.getByText(/\d+ products?/)).toBeVisible();
  });

  test('a search with no matches explains itself', async ({ page }) => {
    await page.goto('/search?q=zzzzzznotathing');
    await expect(page.getByText(/Nothing matched/)).toBeVisible();
  });

  test('category page lists only that category', async ({ page }) => {
    await page.goto('/category/seasonal.christmas');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Seasonal · Christmas');
    await expect(page.getByText(/\d+ products?/)).toBeVisible();
  });

  test('unknown category renders not-found, not an empty list', async ({ page }) => {
    await page.goto('/category/not.a.category');
    // The status line is committed before `notFound()` is reached, because the
    // route streams, so assert on what the shopper actually gets.
    await expect(page.getByText(/could not be found|not found/i).first()).toBeVisible();
    await expect(page.getByRole('link', { name: /Add to cart/ })).toHaveCount(0);
  });

  test('product page is honest about what the source data lacks', async ({ page }) => {
    await page.goto('/search?q=christmas');
    await page.getByRole('heading', { level: 3 }).first().click();

    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByTestId('price').first()).toBeVisible();
    // Brand and GTIN are absent from the dataset and must not be invented.
    await expect(page.getByText('not in source data').first()).toBeVisible();
    // Derived values are labelled as derived.
    await expect(page.getByText('derived').first()).toBeVisible();
  });
});

test.describe('cart', () => {
  test('empty cart offers a way back to the shop', async ({ page }) => {
    await page.goto('/cart');
    await expect(page.getByRole('heading', { name: 'Your cart is empty' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Browse the shop' })).toBeVisible();
  });

  test('adding, changing quantity and removing all work', async ({ page }) => {
    await page.goto('/search?q=christmas');
    await addFirstProductToCart(page);
    await page.goto('/cart');

    await expect(page.getByRole('heading', { name: 'Your cart' })).toBeVisible();
    const quantity = page.getByLabel(/^Quantity of /);
    await expect(quantity).toHaveText('1');

    await page.getByRole('button', { name: /^Increase quantity/ }).click();
    await expect(quantity).toHaveText('2');
    await page.getByRole('button', { name: /^Decrease quantity/ }).click();
    await expect(quantity).toHaveText('1');

    await page.getByRole('button', { name: /^Remove/ }).click();
    await expect(page.getByRole('heading', { name: 'Your cart is empty' })).toBeVisible();
  });

  test('the cart survives a reload', async ({ page }) => {
    await page.goto('/search?q=christmas');
    await addFirstProductToCart(page);
    await page.goto('/cart');
    await page.reload();
    await expect(page.getByLabel(/^Quantity of /)).toHaveText('1');
  });
});

test.describe('checkout', () => {
  test('completes the whole journey and confirms the order', async ({ page }) => {
    await page.goto('/search?q=christmas');
    await addFirstProductToCart(page);

    await page.goto('/cart');
    await page.getByRole('button', { name: 'Proceed to checkout' }).click();

    await expect(page).toHaveURL(/\/checkout\/shipping/);
    await fillShipping(page);
    await page.getByRole('button', { name: 'Continue to payment' }).click();

    await expect(page).toHaveURL(/\/checkout\/payment/);
    // There must be no card number field anywhere in the demo.
    await expect(page.locator('input[name*="card" i]')).toHaveCount(0);
    await expect(page.getByText('mock payment step')).toBeVisible();

    await page.getByRole('button', { name: /Place order/ }).click();

    await expect(page).toHaveURL(/\/checkout\/confirm/, { timeout: 15000 });
    await expect(page.getByRole('heading', { name: 'Order confirmed' })).toBeVisible();
    await expect(page.getByText(/CQ-[A-Z0-9]+/)).toBeVisible();
    await expect(page.getByText('Nothing was actually bought')).toBeVisible();
  });

  test('shipping form reports every missing field', async ({ page }) => {
    await page.goto('/search?q=christmas');
    await addFirstProductToCart(page);
    await page.goto('/checkout/shipping');

    await page.getByRole('button', { name: 'Continue to payment' }).click();
    await expect(page).toHaveURL(/\/checkout\/shipping/);
    await expect(page.getByText('Enter the name for the delivery.')).toBeVisible();
    await expect(page.getByText(/Enter an email address/)).toBeVisible();
    // Focus moves to the first problem rather than only colouring it.
    await expect(page.getByLabel('Full name')).toBeFocused();
  });

  test('a rejected email keeps the shopper on the step', async ({ page }) => {
    await page.goto('/search?q=christmas');
    await addFirstProductToCart(page);
    await page.goto('/checkout/shipping');

    await fillShipping(page);
    await page.getByLabel('Email').fill('not-an-email');
    await page.getByRole('button', { name: 'Continue to payment' }).click();
    await expect(page).toHaveURL(/\/checkout\/shipping/);
    await expect(page.getByLabel('Email')).toBeFocused();
  });

  test('checkout cannot be entered with an empty cart', async ({ page }) => {
    await page.goto('/checkout/shipping');
    await expect(page).toHaveURL(/\/cart/);
  });

  test('payment cannot be reached without an address', async ({ page }) => {
    await page.goto('/search?q=christmas');
    await addFirstProductToCart(page);
    await page.goto('/checkout/payment');
    await expect(page).toHaveURL(/\/checkout\/shipping/);
  });
});

test.describe('event tracking', () => {
  test('the funnel emits each step, stamped with the page it happened on', async ({ page }) => {
    const recorder = await EventRecorder.attach(page);

    await page.goto('/');
    await recorder.waitFor('session_start');
    await recorder.waitFor('page_view');

    await page.getByRole('searchbox', { name: 'Search products' }).fill('christmas');
    await page.getByRole('searchbox', { name: 'Search products' }).press('Enter');
    const search = await recorder.waitFor('search');
    expect(search.properties.query).toBe('christmas');

    await page.getByRole('heading', { level: 3 }).first().click();
    const productView = await recorder.waitFor('product_view');
    expect(productView.product_id).toBeTruthy();
    expect(productView.page).toMatch(/^\/product\//);

    await addFirstProductToCart(page);
    const addToCart = await recorder.waitFor('add_to_cart');
    expect(addToCart.product_id).toBe(productView.product_id);
    expect(addToCart.quantity).toBe(1);

    await page.goto('/cart');
    await page.getByRole('button', { name: 'Proceed to checkout' }).click();
    const checkoutStart = await recorder.waitFor('checkout_start');
    expect(checkoutStart.page).toBe('/cart');

    await fillShipping(page);
    const shippingStep = await recorder.waitFor('shipping_step');
    expect(shippingStep.page).toBe('/checkout/shipping');

    await page.getByRole('button', { name: 'Continue to payment' }).click();
    const paymentStep = await recorder.waitFor('payment_step');
    expect(paymentStep.page).toBe('/checkout/payment');

    await page.getByRole('button', { name: /Place order/ }).click();
    const purchase = await recorder.waitFor('purchase');
    expect(purchase.page).toBe('/checkout/payment');
    expect(purchase.properties.order_id).toMatch(/^CQ-/);
    expect(purchase.price).toBeGreaterThan(0);

    // The whole funnel, in order, from one session.
    const sessions = new Set(recorder.events.map((event) => event.session_id));
    expect(sessions.size).toBe(1);
    const funnelSteps = [
      'session_start',
      'search',
      'product_view',
      'add_to_cart',
      'checkout_start',
      'shipping_step',
      'payment_step',
      'purchase',
    ];
    // A search legitimately emits twice — once as intent from the header box,
    // once with the result count from the results page — so collapse runs of
    // the same step before comparing the order.
    const order = recorder
      .types()
      .filter((type) => funnelSteps.includes(type))
      .filter((type, index, all) => type !== all[index - 1]);
    expect(order).toEqual(funnelSteps);
  });

  test('removing from the cart is measured too', async ({ page }) => {
    const recorder = await EventRecorder.attach(page);
    await page.goto('/search?q=christmas');
    await addFirstProductToCart(page);
    await page.goto('/cart');
    await page.getByRole('button', { name: /^Remove/ }).click();

    const removed = await recorder.waitFor('remove_from_cart');
    expect(removed.product_id).toBeTruthy();
  });

  test('session_start fires once per session, not once per page', async ({ page }) => {
    const recorder = await EventRecorder.attach(page);

    // Each navigation is a full page load, so flush before leaving: queued
    // events would otherwise be discarded with the document.
    await page.goto('/');
    await recorder.waitFor('session_start');
    await page.goto('/cart');
    await recorder.waitForCount('page_view', 2);
    await page.goto('/');

    // The claim under test is that session_start is per-session, not per-page:
    // several page_views, exactly one session_start.
    expect(recorder.ofType('page_view').length).toBeGreaterThanOrEqual(2);
    expect(recorder.ofType('session_start')).toHaveLength(1);
  });
});

test.describe('accessibility', () => {
  test('skip link is first and lands on the main region', async ({ page }) => {
    await page.goto('/');
    await page.keyboard.press('Tab');
    const skip = page.getByRole('link', { name: 'Skip to content' });
    await expect(skip).toBeFocused();
    await skip.press('Enter');
    await expect(page.locator('#main')).toBeVisible();
  });

  test('every form control on the checkout step has a label', async ({ page }) => {
    await page.goto('/search?q=christmas');
    await addFirstProductToCart(page);
    await page.goto('/checkout/shipping');

    // `count()` does not auto-wait, so wait for the form to be there first.
    await page.getByLabel('Full name').waitFor({ state: 'visible' });
    const inputs = page.locator('form input');
    const count = await inputs.count();
    expect(count).toBeGreaterThan(4);
    for (let index = 0; index < count; index++) {
      const id = await inputs.nth(index).getAttribute('id');
      expect(id, 'every input needs an id to be labelled').toBeTruthy();
      await expect(page.locator(`label[for="${id}"]`)).toHaveCount(1);
    }
  });

  test('invalid fields are announced, not just coloured', async ({ page }) => {
    await page.goto('/search?q=christmas');
    await addFirstProductToCart(page);
    await page.goto('/checkout/shipping');
    await page.getByRole('button', { name: 'Continue to payment' }).click();

    const name = page.getByLabel('Full name');
    await expect(name).toHaveAttribute('aria-invalid', 'true');
    const describedBy = await name.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    await expect(page.locator(`#${describedBy}`)).toBeVisible();
  });

  test('the cart is reachable and labelled from the keyboard', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: /^Cart/ })).toBeVisible();
  });
});
