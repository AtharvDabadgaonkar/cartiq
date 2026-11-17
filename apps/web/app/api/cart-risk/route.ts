import { chooseNudge, type CartContext } from '@cartiq/shared';
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { enabledFlagsFor } from '@/lib/flags';
import { scoreAbandonmentRisk } from '@/lib/risk';
import { FREE_SHIPPING_THRESHOLD, shippingFor } from '@/lib/store/shipping';

export const dynamic = 'force-dynamic';

const requestSchema = z.object({
  unitId: z.string().min(1).max(64),
  cartValue: z.number().nonnegative(),
  items: z.number().int().nonnegative(),
  lines: z.number().int().nonnegative(),
  device: z.enum(['desktop', 'mobile', 'tablet', 'unknown']).default('unknown'),
  trafficSource: z.string().max(32).default('direct'),
  productViews: z.number().int().nonnegative().default(0),
  secondsToCart: z.number().int().nonnegative().default(60),
  isNewUser: z.boolean().default(true),
  usedSearch: z.boolean().default(false),
});

/**
 * Scores the cart and returns the nudge, if any, the shopper should see.
 *
 * Server-side on purpose: the model coefficients and the flag configuration
 * both stay off the client, and the decision is made in one place rather than
 * re-derived in the browser.
 */
export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 });
  }

  const parsed = requestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'invalid request', issues: parsed.error.issues.map((i) => i.message) },
      { status: 400 },
    );
  }

  const input = parsed.data;
  const paysShipping = shippingFor(input.cartValue) > 0;
  const gap = Math.max(0, Math.round((FREE_SHIPPING_THRESHOLD - input.cartValue) * 100) / 100);
  const now = new Date();

  const riskScore = scoreAbandonmentRisk({
    device: input.device,
    traffic_source: input.trafficSource,
    // A live visitor has no behavioural segment yet; the model was trained with
    // one, so the most common class is used and that assumption is returned in
    // the response rather than hidden.
    segment: 'new_visitor',
    is_new_user: input.isNewUser,
    used_search: input.usedSearch,
    pays_shipping: paysShipping,
    cart_value: input.cartValue,
    cart_items: input.items,
    cart_lines: input.lines,
    product_views: input.productViews,
    cart_adds: input.lines,
    seconds_to_cart: input.secondsToCart,
    hour_of_day: now.getHours(),
    day_of_week: ((now.getDay() + 6) % 7) + 1,
    gap_to_free_shipping: gap,
  });

  const flags = await enabledFlagsFor(input.unitId);
  const context: CartContext = {
    cartValue: input.cartValue,
    items: input.items,
    riskScore,
    paysShipping,
    gapToFreeShipping: gap,
  };

  return NextResponse.json({
    riskScore,
    nudge: chooseNudge(context, flags),
    enabledFlags: [...flags],
    segmentAssumed: 'new_visitor',
  });
}
