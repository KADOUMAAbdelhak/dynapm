-- V4B per-cell outcome-blind population/continuity audit template.
-- Render {{CELL}} only with one of a..h. Dry-run before every rendered query.
-- Cost note: scans a full cell instance_usage table; dry-run bytes are required.
WITH
usage AS (
  SELECT *
  FROM `google.com:google-cluster-data.clusterdata_2019_{{CELL}}.instance_usage`
  WHERE collection_type = 1
    AND average_usage.cpus >= 0
    AND average_usage.memory >= 0
),
request_events_raw AS (
  SELECT
    collection_id, instance_index, collection_type, time AS request_event_time,
    resource_request.cpus AS request_cpu,
    resource_request.memory AS request_memory
  FROM `google.com:google-cluster-data.clusterdata_2019_{{CELL}}.instance_events`
  WHERE collection_type = 1
    AND resource_request.cpus > 0
    AND resource_request.memory > 0
),
request_events AS (
  SELECT
    collection_id, instance_index, collection_type, request_event_time,
    ANY_VALUE(request_cpu) AS request_cpu,
    ANY_VALUE(request_memory) AS request_memory
  FROM request_events_raw
  GROUP BY collection_id, instance_index, collection_type, request_event_time
  HAVING COUNT(DISTINCT FORMAT('%g/%g', request_cpu, request_memory)) = 1
),
aligned AS (
  SELECT
    u.collection_id, u.instance_index, u.start_time, u.end_time,
    DIV(u.start_time, 300000000) * 300000000 AS bucket_start,
    e.request_cpu, e.request_memory, e.request_event_time
  FROM usage u
  JOIN request_events e
    ON e.collection_id = u.collection_id
   AND e.instance_index = u.instance_index
   AND e.collection_type = u.collection_type
   AND e.request_event_time <= u.start_time
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY u.collection_id, u.instance_index, u.start_time, u.end_time
    ORDER BY e.request_event_time DESC
  ) = 1
),
entity_audit AS (
  SELECT
    collection_id, instance_index,
    COUNT(DISTINCT bucket_start) AS observed_buckets,
    MIN(bucket_start) AS first_bucket,
    MAX(bucket_start) AS last_bucket,
    1 + DIV(MAX(bucket_start) - MIN(bucket_start), 300000000) AS expected_buckets,
    COUNT(DISTINCT FORMAT('%g/%g', request_cpu, request_memory)) AS request_states
  FROM aligned
  GROUP BY collection_id, instance_index
)
SELECT
  '{{CELL}}' AS cell,
  COUNT(*) AS entities_with_aligned_requests,
  COUNTIF(observed_buckets >= 2000
          AND last_bucket - first_bucket >= 604800000000) AS protocol_candidates,
  SUM(observed_buckets) AS aligned_rows,
  SUM(expected_buckets - observed_buckets) AS missing_slots,
  COUNTIF(request_states > 1) AS entities_with_request_changes
FROM entity_audit;
