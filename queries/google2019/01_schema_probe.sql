-- V4B metadata-only schema probe. Dry-run before execution.
-- BILLING_PROJECT is supplied by the guarded acquisition CLI, never committed.
-- Cost note: INFORMATION_SCHEMA probes are typically cheap, but still require
-- an authenticated dry-run; never infer bytes from corpus size.
SELECT
  table_schema,
  table_name,
  column_name,
  field_path,
  data_type
FROM `google.com:google-cluster-data.region-us.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
WHERE table_schema IN (
  'clusterdata_2019_a', 'clusterdata_2019_b', 'clusterdata_2019_c',
  'clusterdata_2019_d', 'clusterdata_2019_e', 'clusterdata_2019_f',
  'clusterdata_2019_g', 'clusterdata_2019_h'
)
AND table_name IN ('instance_usage', 'instance_events')
ORDER BY table_schema, table_name, field_path;
