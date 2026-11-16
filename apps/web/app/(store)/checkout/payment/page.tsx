import type { Metadata } from 'next';
import { PaymentStep } from '@/components/store/checkout-payment';

export const metadata: Metadata = { title: 'Payment' };

export default function PaymentPage() {
  return <PaymentStep />;
}
