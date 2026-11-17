-- Customer grain: the RFM and CLV inputs.
--
-- Only attributed customers appear. A transactional import leaves ~23% of lines
-- without a customer id, and those are deliberately kept in the event log so
-- revenue reconciles — but they cannot be scored, so they are excluded here and
-- the exclusion is reported rather than silently applied.
DROP VIEW IF EXISTS mart_customers CASCADE;

CREATE VIEW mart_customers AS
WITH bounds AS (
    -- Recency is measured against the last day in the data, not today: the
    -- dataset ends in 2011, so "days since last order" against the wall clock
    -- would make every customer maximally lapsed.
    SELECT data_source, MAX(ordered_on) AS as_of
    FROM int_orders
    GROUP BY data_source
),
per_customer AS (
    SELECT
        o.user_id,
        o.data_source,
        COUNT(DISTINCT o.order_id)                       AS frequency,
        SUM(o.revenue)                                   AS monetary,
        AVG(o.revenue)                                   AS avg_order_value,
        SUM(o.items)                                     AS items,
        MIN(o.ordered_on)                                AS first_order_on,
        MAX(o.ordered_on)                                AS last_order_on,
        MAX(o.country)                                   AS country
    FROM int_orders o
    WHERE o.user_id IS NOT NULL
    GROUP BY o.user_id, o.data_source
)
SELECT
    c.user_id,
    c.data_source,
    b.as_of,
    (b.as_of - c.last_order_on)                          AS recency_days,
    c.frequency,
    ROUND(c.monetary::numeric, 2)                        AS monetary,
    ROUND(c.avg_order_value::numeric, 2)                 AS avg_order_value,
    c.items,
    c.first_order_on,
    c.last_order_on,
    (c.last_order_on - c.first_order_on)                 AS tenure_days,
    c.country,
    -- Simple historical CLV: observed revenue to date. No projection, because a
    -- projected CLV needs a churn model this phase does not have.
    ROUND(c.monetary::numeric, 2)                        AS clv_historical,
    -- Quintile scores, 5 = best. Recency is inverted: fewer days is better.
    (6 - NTILE(5) OVER (PARTITION BY c.data_source ORDER BY (b.as_of - c.last_order_on) ASC))
                                                         AS r_score,
    NTILE(5) OVER (PARTITION BY c.data_source ORDER BY c.frequency ASC)  AS f_score,
    NTILE(5) OVER (PARTITION BY c.data_source ORDER BY c.monetary ASC)   AS m_score
FROM per_customer c
JOIN bounds b ON b.data_source = c.data_source;

COMMENT ON VIEW mart_customers IS
  'Attributed customers with RFM quintile scores and historical CLV. Recency is '
  'measured against the last date in the data, not the wall clock.';
