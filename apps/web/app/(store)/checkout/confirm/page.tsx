import type { Metadata } from 'next';
import { ConfirmStep } from '@/components/store/checkout-confirm';

export const metadata: Metadata = { title: 'Order confirmed' };

export default function ConfirmPage() {
  return <ConfirmStep />;
}
