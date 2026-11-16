import type { Metadata } from 'next';
import { ShippingStep } from '@/components/store/checkout-shipping';

export const metadata: Metadata = { title: 'Shipping' };

export default function ShippingPage() {
  return <ShippingStep />;
}
