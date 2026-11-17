-- One row per session, with the attributes every funnel slice needs and a
-- boolean for each funnel step the session reached.
--
-- A step is "reached" if the session emitted ANY event for it. Steps are
-- monotonic by construction in the storefront and the simulator, but this view
-- does not assume that: `max_step_depth` is derived from the deepest step the
-- session actually reached, so an out-of-order log cannot inflate the funnel.
-- Dropped first: CREATE OR REPLACE cannot insert a column mid-list, which
-- makes every column addition a schema fight. Models are applied in
-- dependency order, so CASCADE only drops views this runner rebuilds.
-- MATERIALISED on purpose. Every diagnosis query starts from session grain,
-- and recomputing it from 1.6M events per request took ~7s for the funnel
-- alone. Materialising plus indexing brings the whole dashboard inside its
-- 2-second budget. `scripts/build_models.py` rebuilds it, so it is refreshed
-- by `make migrate` after any load.
DROP MATERIALIZED VIEW IF EXISTS int_sessions CASCADE;

CREATE MATERIALIZED VIEW int_sessions AS
WITH flags AS (
    SELECT
        e.session_id,
        e.data_source,
        e.simulation_run_id,
        MIN(e.occurred_at)                                    AS started_at,
        MAX(e.occurred_at)                                    AS ended_at,
        MIN(e.occurred_on)                                    AS session_date,
        -- Attributes are stamped on every event; any row carries them.
        MAX(e.device::text)                                   AS device,
        MAX(e.traffic_source::text)                           AS traffic_source,
        BOOL_OR(e.is_new_user)                                AS is_new_user,
        MAX(e.user_id)                                        AS user_id,
        MAX(e.properties ->> 'segment')                       AS segment,
        MAX(e.properties ->> 'country')                       AS country,
        -- The experiment assignments stamped at event time.
        MAX(e.experiment_assignments::text)                   AS experiment_assignments,

        BOOL_OR(e.event_type = 'session_start')               AS reached_visit,
        BOOL_OR(e.event_type IN ('page_view', 'search'))      AS reached_browse,
        BOOL_OR(e.event_type = 'product_view')                AS reached_product_view,
        BOOL_OR(e.event_type = 'add_to_cart')                 AS reached_add_to_cart,
        BOOL_OR(e.event_type = 'checkout_start')              AS reached_checkout,
        BOOL_OR(e.event_type = 'shipping_step')               AS reached_shipping,
        BOOL_OR(e.event_type = 'payment_step')                AS reached_payment,
        BOOL_OR(e.event_type = 'purchase')                    AS reached_purchase,

        BOOL_OR(e.event_type = 'search')                      AS used_search,
        COUNT(*) FILTER (WHERE e.event_type = 'product_view')  AS product_views,
        COUNT(*) FILTER (WHERE e.event_type = 'add_to_cart')   AS cart_adds,
        -- Revenue has to be source-aware. A transactional import emits one
        -- purchase event PER INVOICE LINE carrying a unit price, while the
        -- storefront and the simulator emit one purchase event PER ORDER
        -- carrying the order total. Summing price * quantity across both would
        -- multiply simulated revenue by the basket size.
        COALESCE(
            CASE
                WHEN e.data_source = 'REAL_DATASET'
                    THEN SUM(e.price * e.quantity) FILTER (WHERE e.event_type = 'purchase')
                ELSE SUM(e.price) FILTER (WHERE e.event_type = 'purchase')
            END,
            0
        ) AS revenue,
        COALESCE(SUM(e.quantity) FILTER (WHERE e.event_type = 'purchase'), 0) AS items_purchased
    FROM stg_events e
    GROUP BY e.session_id, e.data_source, e.simulation_run_id
)
SELECT
    session_id,
    data_source,
    simulation_run_id,
    started_at,
    ended_at,
    session_date,
    device,
    traffic_source,
    is_new_user,
    user_id,
    segment,
    country,
    experiment_assignments,
    reached_visit,
    reached_browse,
    reached_product_view,
    reached_add_to_cart,
    reached_checkout,
    reached_shipping,
    reached_payment,
    reached_purchase,
    used_search,
    product_views,
    cart_adds,
    revenue,
    items_purchased,
    reached_purchase AS converted,
    -- Deepest step index reached: 0 = visit only, 7 = purchase.
    (CASE WHEN reached_purchase    THEN 7
          WHEN reached_payment     THEN 6
          WHEN reached_shipping    THEN 5
          WHEN reached_checkout    THEN 4
          WHEN reached_add_to_cart THEN 3
          WHEN reached_product_view THEN 2
          WHEN reached_browse      THEN 1
          ELSE 0 END)                                         AS max_step_depth,
    -- Abandonment is specifically a cart that never reached purchase.
    (reached_add_to_cart AND NOT reached_purchase)             AS abandoned_cart
FROM flags;

CREATE INDEX int_sessions_source_date_idx
    ON int_sessions (data_source, session_date);
CREATE INDEX int_sessions_source_device_idx
    ON int_sessions (data_source, device);
CREATE INDEX int_sessions_session_idx
    ON int_sessions (session_id);
CREATE INDEX int_sessions_cart_idx
    ON int_sessions (data_source) WHERE reached_add_to_cart;

COMMENT ON MATERIALIZED VIEW int_sessions IS
  'Session grain. Always filter on data_source: a transactional source records '
  'only purchases, so its sessions are 100% converted by construction and must '
  'never be mixed into a funnel or conversion rate.';
