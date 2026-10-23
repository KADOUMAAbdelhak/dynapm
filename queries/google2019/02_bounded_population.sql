-- V4B bounded, outcome-blind population audit for cells a and b.
-- Required: dry-run and maximum_bytes_billed guard before execution.
-- Cost note: instance_usage/instance_events are not documented as partitioned
-- on start_time; the [7d,15d) predicate may not reduce billed bytes.
-- Fixed validation interval: trace days [7, 15), enough to exercise 30%
-- bootstrap plus trailing/future 24h windows without using method outcomes.
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
    cell, collection_id, instance_index, collection_type, time AS request_event_time,
    resource_request.cpus AS request_cpu,
    resource_request.memory AS request_memory
  FROM events
  WHERE collection_type = 1  -- ALLOC_SET only; avoids task/alloc double counting.
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
)
SELECT
  *,
  expected_buckets - observed_buckets AS missing_buckets,
  request_states > 1 AS has_request_change,
  observed_buckets < expected_buckets AS has_missing_slot,
  FARM_FINGERPRINT(CONCAT(cell, '|', CAST(collection_id AS STRING), '|',
                          CAST(instance_index AS STRING))) AS selection_hash
FROM entity_audit
WHERE observed_buckets >= 2000
  AND last_bucket - first_bucket >= 604800000000
ORDER BY cell, selection_hash, collection_id, instance_index;
