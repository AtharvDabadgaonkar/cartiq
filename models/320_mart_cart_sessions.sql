-- Training table for the abandonment-risk model: one row per session that
-- added something to a cart.
--
-- LEAKAGE IS THE WHOLE DESIGN PROBLEM HERE. The model has to score a cart at
-- the moment it is created, so every feature must be knowable then. Anything
-- that happens afterwards — reaching checkout, the shipping step, the payment
-- step — is excluded, because including it would produce a model with a
-- beautiful AUC that cannot be deployed: by the time those are observable the
-- shopper has already decided.
DROP VIEW IF EXISTS mart_cart_sessions CASCADE;

CREATE VIEW mart_cart_sessions AS
WITH cart AS (
    SELECT
        e.session_id,
        e.data_source,
        -- Value of what was put in the cart. Add-to-cart events are line
        -- grained in every source, so this rule is uniform.
        SUM(e.price * COALESCE(e.quantity, 1))        AS cart_value,
        SUM(COALESCE(e.quantity, 1))                  AS cart_items,
        COUNT(*)                                      AS cart_lines,
        MIN(e.occurred_at)                            AS first_cart_at,
        e.simulation_run_id
    FROM stg_events e
    WHERE e.event_type = 'add_to_cart'
    -- simulation_run_id matters: two loaded runs can reuse a session id, and
    -- without it their carts merge into one impossible session.
    GROUP BY e.session_id, e.data_source, e.simulation_run_id
)
SELECT
    s.session_id,
    s.data_source,
    s.session_date,
    -- Target.
    s.abandoned_cart                                           AS abandoned,

    -- Context known when the cart is created.
    s.device,
    s.traffic_source,
    s.segment,
    COALESCE(s.is_new_user, false)                             AS is_new_user,
    s.used_search,
    s.product_views,
    s.cart_adds,
    ROUND(c.cart_value::numeric, 2)                            AS cart_value,
    c.cart_items,
    c.cart_lines,
    -- Seconds from the session start to the first add-to-cart: a proxy for
    -- deliberation. A long browse before carting reads differently from an
    -- immediate add.
    EXTRACT(EPOCH FROM (c.first_cart_at - s.started_at))::int  AS seconds_to_cart,
    EXTRACT(HOUR FROM s.started_at)::int                       AS hour_of_day,
    EXTRACT(ISODOW FROM s.started_at)::int                     AS day_of_week,
    -- Whether shipping will be charged, which is the single most actionable
    -- thing a nudge can speak to.
    (c.cart_value < 40.0)                                      AS pays_shipping,
    ROUND(GREATEST(40.0 - c.cart_value, 0)::numeric, 2)        AS gap_to_free_shipping,
    s.experiment_assignments
FROM int_sessions s
JOIN cart c
  ON c.session_id = s.session_id
 AND c.data_source = s.data_source
 -- IS NOT DISTINCT FROM, because the run id is NULL for non-simulated rows
 -- and NULL = NULL would drop every one of them.
 AND c.simulation_run_id IS NOT DISTINCT FROM s.simulation_run_id
WHERE s.reached_add_to_cart;

COMMENT ON VIEW mart_cart_sessions IS
  'One row per carting session with only features knowable at cart creation. '
  'Post-cart funnel steps are deliberately excluded to prevent target leakage.';
