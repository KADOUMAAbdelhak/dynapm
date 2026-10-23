-- V4B.3 zero-cost minimal instance_usage extract template.
-- Render {{CELL}} with a frozen plan cell only. Dry-run before execution.
-- Selects leaf columns only (never SELECT * or whole average_usage struct).
-- collection_type = 1 (ALLOC_SET). Unpartitioned: predicates do not reduce bytes.
SELECT
  start_time,
  end_time,
  collection_id,
  instance_index,
  collection_type,
  average_usage.cpus AS average_cpu,
  average_usage.memory AS average_memory
FROM `google.com:google-cluster-data.clusterdata_2019_{{CELL}}.instance_usage`
WHERE collection_type = 1;
