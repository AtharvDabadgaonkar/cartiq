-- Purchase popularity per product, derived from the event log.
-- The storefront uses it to order "best selling" and to pick related items;
-- Phase 4's marts build on the same definition rather than restating it.
CREATE OR REPLACE VIEW int_product_popularity AS
SELECT
    p.id                                                       AS product_id,
    COALESCE(SUM(e.quantity) FILTER (WHERE e.event_type = 'purchase'), 0)::bigint
                                                               AS units_sold,
    COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type = 'purchase')
                                                               AS orders,
    COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_type = 'product_view')
                                                               AS views,
    MAX(e.timestamp) FILTER (WHERE e.event_type = 'purchase')  AS last_sold_at
FROM products p
LEFT JOIN events e ON e.product_id = p.id
GROUP BY p.id;

COMMENT ON VIEW int_product_popularity IS
  'Units sold, orders and views per product across ALL data sources. Filter '
  'events by data_source upstream when a figure must be real-only.';
