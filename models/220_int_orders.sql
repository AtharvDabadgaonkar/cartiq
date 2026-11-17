-- One row per order.
--
-- The order key is `properties->>'order_id'`, which every source sets: the
-- invoice number for an import, the generated reference for the storefront and
-- the simulator. Grouping on it means an order is an order regardless of how
-- many events produced it.
-- Materialised: this aggregates every purchase event, and the KPI tiles
-- query it on each page load.
DROP MATERIALIZED VIEW IF EXISTS int_orders CASCADE;

CREATE MATERIALIZED VIEW int_orders AS
SELECT
    e.properties ->> 'order_id'                       AS order_id,
    MIN(e.session_id)                                 AS session_id,
    MAX(e.user_id)                                    AS user_id,
    e.data_source,
    MIN(e.occurred_at)                                AS ordered_at,
    MIN(e.occurred_on)                                AS ordered_on,
    MAX(e.device::text)                               AS device,
    MAX(e.traffic_source::text)                       AS traffic_source,
    MAX(e.properties ->> 'country')                   AS country,
    COUNT(*)                                          AS line_count,
    COALESCE(SUM(e.quantity), 0)                      AS items,
    -- See int_sessions: line-grain sources carry a unit price, order-grain
    -- sources carry the order total.
    CASE
        WHEN e.data_source = 'REAL_DATASET' THEN SUM(e.price * e.quantity)
        ELSE SUM(e.price)
    END                                               AS revenue
FROM stg_events e
WHERE e.event_type = 'purchase'
  AND e.properties ->> 'order_id' IS NOT NULL
GROUP BY e.properties ->> 'order_id', e.data_source;

CREATE INDEX int_orders_source_idx ON int_orders (data_source, ordered_on);
CREATE INDEX int_orders_session_idx ON int_orders (session_id);

COMMENT ON MATERIALIZED VIEW int_orders IS
  'Order grain across every source. Revenue is source-aware because a '
  'transactional import is line-grained and the storefront is order-grained.';
