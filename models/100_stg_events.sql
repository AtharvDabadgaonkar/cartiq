-- Staging layer for the raw event log: one row per event, renamed to the
-- names the rest of the models use, with the provenance label carried through.
-- Dropped first: CREATE OR REPLACE cannot insert a column mid-list, which
-- makes every column addition a schema fight. Models are applied in
-- dependency order, so CASCADE only drops views this runner rebuilds.
DROP VIEW IF EXISTS stg_events CASCADE;

CREATE VIEW stg_events AS
SELECT
    event_id,
    event_type,
    timestamp                              AS occurred_at,
    timestamp::date                        AS occurred_on,
    user_id,
    session_id,
    device,
    traffic_source,
    is_new_user,
    page,
    product_id,
    price,
    quantity,
    experiment_assignments,
    properties,
    source                                 AS data_source,
    simulation_run_id
FROM events;

COMMENT ON VIEW stg_events IS
  'Renamed, typed view over the raw event log. Always filter on data_source: '
  'REAL_DATASET, SIMULATED and LIVE_DEMO must never be mixed in a reported number '
  'without saying so.';
