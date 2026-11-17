-- Funnel at step grain, sliceable without re-deriving the step definitions.
--
-- One row per session per step the session REACHED, so a count of sessions at
-- a step is a plain COUNT and the console cannot accidentally invent its own
-- definition of "reached".
-- Materialised: eight rows per session, read on every funnel render.
DROP MATERIALIZED VIEW IF EXISTS mart_funnel CASCADE;

CREATE MATERIALIZED VIEW mart_funnel AS
SELECT
    s.session_id,
    s.data_source,
    s.session_date,
    s.device,
    s.traffic_source,
    s.is_new_user,
    s.segment,
    s.converted,
    s.revenue,
    step.step_key,
    step.step_index,
    step.step_label
FROM int_sessions s
CROSS JOIN LATERAL (
    VALUES
        ('visit',        0, 'Visit',            s.reached_visit),
        ('browse',       1, 'Search / Browse',  s.reached_browse),
        ('product_view', 2, 'Product View',     s.reached_product_view),
        ('add_to_cart',  3, 'Add to Cart',      s.reached_add_to_cart),
        ('checkout',     4, 'Checkout Start',   s.reached_checkout),
        ('shipping',     5, 'Shipping',         s.reached_shipping),
        ('payment',      6, 'Payment',          s.reached_payment),
        ('purchase',     7, 'Purchase',         s.reached_purchase)
) AS step(step_key, step_index, step_label, reached)
WHERE step.reached;

CREATE INDEX mart_funnel_slice_idx
    ON mart_funnel (data_source, step_index, session_date);
CREATE INDEX mart_funnel_dims_idx
    ON mart_funnel (data_source, device, traffic_source, segment);

COMMENT ON MATERIALIZED VIEW mart_funnel IS
  'One row per session per reached funnel step. Step order and labels match '
  'packages/shared/src/events.ts FUNNEL_STEPS.';
