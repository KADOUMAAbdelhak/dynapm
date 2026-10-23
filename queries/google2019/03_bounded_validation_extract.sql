-- V4B bounded canonical-source extract for cells a and b.
-- REQUIRED: successful dry-run + explicit maximum_bytes_billed before execution.
-- Cost note: time predicates may not prune unpartitioned cell tables.
-- Deterministic validation sample: up to 2 hash-ranked ALLOC_SET instances per
-- (cell, request-change, missing-slot) metadata stratum. Selection never uses
-- Static/PW/Full-Rewrite outcomes or profile fidelity.
WITH
usage AS (
  SELECT 'a' AS cell, * FROM `google.com:google-cluster-data.clusterdata_2019_a.instance_usage`
  WHERE start_time >= 604800000000 AND start_time < 1296000000000
  UNION ALL
  SELECT 'b' AS cell, * FROM `google.com:google-cluster-data.clusterdata_2019_b.instance_usage`
  WHERE start_time >= 604800000000 AND start_time < 1296000000000
),
events AS (
  SELECT 'a' AS cell, * FROM `google.com:google-cluster-data.clusterdata_2019_a.instance_events`
  WHERE time < 1296000000000
  UNION ALL
  SELECT 'b' AS cell, * FROM `google.com:google-cluster-data.clusterdata_2019_b.instance_events`
  WHERE time < 1296000000000
),
request_events_raw AS (
  SELECT
    cell, collection_id, instance_index, collection_type,
    time AS request_event_time,
    resource_request.cpus AS request_cpu,
    resource_request.memory AS request_memory
  FROM events
  WHERE collection_type = 1
    AND resource_request.cpus > 0
    AND resource_request.memory > 0
),
request_events AS (
  -- Unambiguous same-timestamp requests only. Inner COUNT uses base columns
  -- (not ANY_VALUE aliases) to avoid BigQuery "aggregations of aggregations".
  SELECT * EXCEPT(n_distinct_requests)
  FROM (
    SELECT
      cell, collection_id, instance_index, collection_type, request_event_time,
      ANY_VALUE(request_cpu) AS request_cpu,
      ANY_VALUE(request_memory) AS request_memory,
      COUNT(DISTINCT FORMAT('%g/%g', request_cpu, request_memory)) AS n_distinct_requests
    FROM request_events_raw
    GROUP BY cell, collection_id, instance_index, collection_type, request_event_time
  )
  WHERE n_distinct_requests = 1
),
aligned AS (
  SELECT
    u.cell, u.collection_id, u.instance_index, u.collection_type,
    u.start_time, u.end_time,
    u.average_usage.cpus AS average_cpu,
    u.average_usage.memory AS average_memory,
    e.request_cpu, e.request_memory, e.request_event_time,
    DIV(u.start_time, 300000000) * 300000000 AS bucket_start
  FROM usage u
  JOIN request_events e
    ON e.cell = u.cell
   AND e.collection_id = u.collection_id
   AND e.instance_index = u.instance_index
   AND e.collection_type = u.collection_type
   AND e.request_event_time <= u.start_time
  WHERE u.collection_type = 1
    AND u.average_usage.cpus >= 0
    AND u.average_usage.memory >= 0
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY u.cell, u.collection_id, u.instance_index, u.start_time, u.end_time
    ORDER BY e.request_event_time DESC
  ) = 1
),
entity_audit AS (
  SELECT
    cell, collection_id, instance_index,
    COUNT(DISTINCT bucket_start) AS observed_buckets,
    MIN(bucket_start) AS first_bucket,
    MAX(bucket_start) AS last_bucket,
    COUNT(DISTINCT FORMAT('%g/%g', request_cpu, request_memory)) AS request_states,
    1 + DIV(MAX(bucket_start) - MIN(bucket_start), 300000000) AS expected_buckets
  FROM aligned
  GROUP BY cell, collection_id, instance_index
),
eligible AS (
  SELECT
    *,
    request_states > 1 AS has_request_change,
    observed_buckets < expected_buckets AS has_missing_slot,
    FARM_FINGERPRINT(CONCAT(cell, '|', CAST(collection_id AS STRING), '|',
                            CAST(instance_index AS STRING))) AS selection_hash
  FROM entity_audit
  WHERE observed_buckets >= 2000
    AND last_bucket - first_bucket >= 604800000000
),
chosen AS (
  SELECT *
  FROM eligible
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cell, has_request_change, has_missing_slot
    ORDER BY selection_hash, collection_id, instance_index
  ) <= 2
)
SELECT
  a.cell,
  a.collection_id,
  a.instance_index,
  a.collection_type,
  a.start_time,
  a.end_time,
  a.bucket_start,
  a.average_cpu,
  a.average_memory,
  a.request_cpu,
  a.request_memory,
  a.request_event_time,
  c.has_request_change,
  c.has_missing_slot,
  c.selection_hash,
  CONCAT(
    'google.com:google-cluster-data.clusterdata_2019_',
    a.cell, '.instance_usage'
  ) AS usage_source_table,
  CONCAT(
    'google.com:google-cluster-data.clusterdata_2019_',
    a.cell, '.instance_events'
  ) AS request_source_table
FROM aligned a
JOIN chosen c USING (cell, collection_id, instance_index)
ORDER BY cell, collection_id, instance_index, bucket_start, end_time DESC;
