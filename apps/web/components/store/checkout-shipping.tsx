'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useCart } from '@/components/providers/cart-provider';
import { useTracker } from '@/components/providers/tracking-provider';
import { CheckoutSteps } from '@/components/store/checkout-steps';
import { OrderSummary } from '@/components/store/order-summary';
import { Button } from '@/components/ui/button';
import {
  EMPTY_SHIPPING,
  readShipping,
  saveShipping,
  validateShipping,
  type ShippingDetails,
  type ShippingErrors,
} from '@/lib/store/checkout';

const FIELDS: {
  name: keyof ShippingDetails;
  label: string;
  type?: string;
  autoComplete: string;
  optional?: boolean;
}[] = [
  { name: 'fullName', label: 'Full name', autoComplete: 'name' },
  { name: 'email', label: 'Email', type: 'email', autoComplete: 'email' },
  { name: 'address1', label: 'Address', autoComplete: 'address-line1' },
  { name: 'address2', label: 'Address line 2', autoComplete: 'address-line2', optional: true },
  { name: 'city', label: 'Town or city', autoComplete: 'address-level2' },
  { name: 'postcode', label: 'Postcode', autoComplete: 'postal-code' },
  { name: 'country', label: 'Country', autoComplete: 'country-name' },
];

export function ShippingStep() {
  const router = useRouter();
  const { lines, itemCount, subtotal, ready } = useCart();
  const tracker = useTracker();
  const [details, setDetails] = useState<ShippingDetails>(EMPTY_SHIPPING);
  const [errors, setErrors] = useState<ShippingErrors>({});
  const tracked = useRef(false);

  useEffect(() => {
    setDetails(readShipping() ?? EMPTY_SHIPPING);
  }, []);

  // Reaching this step IS the shipping funnel step.
  useEffect(() => {
    if (tracked.current || !ready || lines.length === 0) return;
    tracked.current = true;
    tracker.track('shipping_step', { price: subtotal, quantity: itemCount });
  }, [tracker, ready, lines.length, subtotal, itemCount]);

  useEffect(() => {
    if (ready && lines.length === 0) router.replace('/cart');
  }, [ready, lines.length, router]);

  if (!ready || lines.length === 0) return null;

  return (
    <div className="space-y-8">
      <CheckoutSteps current="shipping" />
      <h1 className="text-2xl font-semibold tracking-tight">Where should it go?</h1>

      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            const found = validateShipping(details);
            setErrors(found);
            if (Object.keys(found).length > 0) {
              // Move focus to the first problem, rather than only colouring it.
              const firstField = FIELDS.find((field) => found[field.name]);
              if (firstField) document.getElementById(firstField.name)?.focus();
              return;
            }
            saveShipping(details);
            router.push('/checkout/payment');
          }}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {FIELDS.map((field) => {
              const error = errors[field.name];
              const wide = field.name === 'address1' || field.name === 'address2';
              return (
                <div key={field.name} className={wide ? 'sm:col-span-2' : undefined}>
                  <label htmlFor={field.name} className="block text-sm font-medium">
                    {field.label}
                    {field.optional && (
                      <span className="text-muted-foreground ml-1 font-normal">(optional)</span>
                    )}
                  </label>
                  <input
                    id={field.name}
                    name={field.name}
                    type={field.type ?? 'text'}
                    autoComplete={field.autoComplete}
                    value={details[field.name]}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={error ? `${field.name}-error` : undefined}
                    onChange={(event) =>
                      setDetails((current) => ({ ...current, [field.name]: event.target.value }))
                    }
                    className={`bg-surface mt-1 h-10 w-full rounded-md border px-3 text-sm ${
                      error ? 'border-clay' : 'border-input'
                    }`}
                  />
                  {error && (
                    <p id={`${field.name}-error`} className="text-clay mt-1 text-xs">
                      {error}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          <Button type="submit" size="lg" className="mt-6 w-full sm:w-auto">
            Continue to payment
          </Button>
        </form>

        <OrderSummary subtotal={subtotal} itemCount={itemCount} />
      </div>
    </div>
  );
}
