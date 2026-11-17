import 'server-only';
import model from '@/lib/model/abandonment-model.json';

/**
 * Scores a cart with the exported logistic abandonment model.
 *
 * The model is trained in Python and exported as plain numbers (see
 * `scripts/train_abandonment.py`). Re-implementing the scoring here, rather
 * than calling a Python service, keeps the storefront deployable on its own —
 * and a logistic regression is only a dot product once the preprocessing is
 * applied.
 */

export interface CartFeatures {
  device: string;
  traffic_source: string;
  segment: string;
  is_new_user: boolean;
  used_search: boolean;
  pays_shipping: boolean;
  cart_value: number;
  cart_items: number;
  cart_lines: number;
  product_views: number;
  cart_adds: number;
  seconds_to_cart: number;
  hour_of_day: number;
  day_of_week: number;
  gap_to_free_shipping: number;
}

/** Column order must match the exported `feature_names`. */
function buildVector(features: CartFeatures): number[] {
  const vector: number[] = [];

  // One-hot, with the first category dropped as the reference level.
  for (const feature of model.categorical.features) {
    const categories = (model.categorical.categories as Record<string, string[]>)[feature] ?? [];
    const value = String((features as unknown as Record<string, unknown>)[feature] ?? '');
    for (const category of categories.slice(model.categorical.drop_first ? 1 : 0)) {
      vector.push(value === category ? 1 : 0);
    }
  }

  // Standard-scaled numerics, in the exported order.
  model.numeric.features.forEach((feature, index) => {
    const raw = (features as unknown as Record<string, unknown>)[feature];
    const numeric = typeof raw === 'boolean' ? (raw ? 1 : 0) : Number(raw ?? 0);
    const mean = model.numeric.mean[index] ?? 0;
    const scale = model.numeric.scale[index] || 1;
    vector.push((numeric - mean) / scale);
  });

  return vector;
}

/** Predicted probability that this cart is abandoned, in [0, 1]. */
export function scoreAbandonmentRisk(features: CartFeatures): number {
  const vector = buildVector(features);
  if (vector.length !== model.coefficients.length) {
    // A shape mismatch means the export and this scorer disagree. Returning a
    // wrong probability would silently mis-target every nudge, so refuse.
    throw new Error(
      `risk model shape mismatch: built ${vector.length} features, model expects ${model.coefficients.length}`,
    );
  }
  let z = model.intercept;
  for (let i = 0; i < vector.length; i++) z += vector[i]! * model.coefficients[i]!;
  return 1 / (1 + Math.exp(-z));
}

export const RISK_MODEL_META = {
  model: model.model,
  trainedOnRows: model.trained_on_rows,
  rocAuc: model.roc_auc,
} as const;
