-- V4B.3 zero-cost minimal instance_events extract template.
-- Render {{CELL}} with a frozen plan cell only. Dry-run before execution.
-- Selects leaf request columns only (never whole resource_request struct).
-- Positive CPU+memory requests; ALLOC_SET only. Local causal alignment later.
SELECT
  time,
  collection_id,
  instance_index,
  collection_type,
  resource_request.cpus AS request_cpu,
  resource_request.memory AS request_memory
FROM `google.com:google-cluster-data.clusterdata_2019_{{CELL}}.instance_events`
WHERE collection_type = 1
  AND resource_request.cpus > 0
  AND resource_request.memory > 0;
