-- Staging layer for the raw event log: one row per event, renamed to the
-- names the rest of the models use, with the provenance label carried through.
CREATE OR REPLACE VIEW stg_events AS
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
