# V8C.5 prospective direct-Service transport qualification

RESTART_FULL_18_WITH_AMENDED_TRANSPORT. Qualification only; no claim treatment or integration was launched. All original attempts 1–9 are excluded from primary application-endpoint analysis, including previously transport-valid records. A new campaign must start at slot 1; no old/new mixing.

Scientific source `fe3b870149a156e7fecb88741d51cfb5c1ed86d7`; previous harness `d0ffc346e13d22f7b3d072fc59378831a668b3f2`; transport review `85da10df01db917e496b72a1311c3ae622ce0442`; implementation `b3fd0d1fa095dbaa13c2b035624d6336b24d60ca`.

Amendment SHA-256 `286c6bb99d5e293c5ce6085ce7d80c9c258518063ec66d0a57bcc112e6ed65f8`. PROSPECTIVE_SEAL-v2.json binds the spec and executable code before the accepted diagnostics.

## Architecture and persistence

The generator runs as a separate Pod on the control-plane node with fixed 1000m CPU and 512 MiB request/limit. The application stays on the worker with its frozen CPU=request=limit, variable memory reservation and common 1024 MiB cap. Generator resources were fixed from the engineering concurrency/I/O budget before outcomes, not selected for policy performance.

Every workload request is generator Pod -> Service DNS/ClusterIP -> application Pod. No kubectl port-forward process is created. The same pinned workload image supplies Python; a provenance-bound ConfigMap supplies the standalone generator. No replacement image is pulled or built. The exact query work, rates, seeds, 32-request concurrency cap, no-retry rule and socket timeout are preserved.

Request results are flushed/fsynced individually to node hostPath storage, with exclusive OWNER and atomic START/DONE seals. The generator exits cleanly. The host then copies sealed bytes through the independent Docker control/file-copy path and validates SHA/counts before cluster deletion. If export or observation fails, the cluster/node files and recovery configuration are retained. Offline fault injection proves export resume does not rerun requests or destroy sealed data. A deliberate 15-second host-observer pause in neutral qualification left all 7,200 records intact; power and resource-clock observers continued independently.

## Accepted non-claim qualification

All rows below are DIAGNOSTIC_NON_CLAIM. Expected counts are scheduled offers; sent attempts and unsent concurrency-cap drops are separately reconciled. Application degradation is not a missing measurement. Sealing may follow the fixed offered window while final client attempts drain; late completions do not extend that window.

| Condition | Application CPU / memory reservation | Offered window / seal after | Offers / records | Sent attempts | Unsent cap drops | Outcomes |
|---|---|---:|---:|---:|---:|---|
| neutral | 1000m / 512 MiB | 600 / 600.011756 s | 7200 / 7200 | 7200 | 0 | {'success': 7200} |
| low | 70m / 64 MiB | 900 / 907.618818 s | 10800 / 10800 | 5646 | 5154 | {'success': 635, 'overload_drop': 5154, 'request_timeout': 4201, 'transport_error': 810} |
| periodic_transition | 70m / 64 MiB | 900 / 900.012426 s | 6300 / 6300 | 3737 | 2563 | {'success': 1165, 'overload_drop': 2563, 'request_timeout': 2148, 'transport_error': 424} |

Neutral and low used 12 RPS / 96 MiB. The 15-minute phase diagnostic used 450 s at 12 RPS / 96 MiB then 450 s at 2 RPS / 32 MiB. This is a bounded engineering condition; actual claim periodic phases remain 900/900 s and total treatment timing remains 900 s cooldown + 1800 s reference warm-up + 1800 s exposure.

All expected IDs, offer offsets, phases and work parameters independently reconstructed; zero missing or duplicate records. Every generator exited 0 with zero restarts. Application Pod UID/restarts, Service DNS/IP/endpoints, Kubernetes events, node conditions and cgroup/clock evidence were independently checked. Guard releases and the original 2 s / 30 s limits passed. Raw Service errors and connection/response deadlines remain separately recorded; they are not silently relabelled application errors.

## Measurement and comparability

Latency retains scheduled-offer to complete-response-body receipt, before JSON validation/socket close, using the client local monotonic clock. Network attempt latency is a separate secondary field. Success uses the same HTTP 200/ok/iteration/memory checks. SLO remains failed offers plus successful latencies above 250 ms, divided by all offers. Successful p95 quantile and completion-window throughput arithmetic are unchanged. Every future primary window remains [0,1800), with [0,300) and [300,1800) descriptive slices.

The path and client location change. New measurements include in-cluster DNS/Service routing and omit host/port-forward latency and failure modes. Thus network-sensitive measured quantities are not directly numerically comparable to old slots 1–9, even though arithmetic is preserved. All new cells must use this one versioned Service-client definition. The legacy application_failures numeric key is a total failed-client-attempt aggregate for compatibility; it is not a causal assertion. New fields separately identify application HTTP/body errors, Service transport errors, connection deadlines and response deadlines whose precise cause remains unresolved.

A timeout is an observed deadline, not proof of application fault. An explicit connection/reset/body-transport failure is not labelled application_error. Service/readiness failures can be observed operational outcomes on the declared Service boundary; lost generator data, failed provenance or unverifiable control/resource state are harness failures. No settling threshold, practical superiority margin, compression factor or treatment redesign was introduced.

## Preserved engineering attempts and tests

The first preflight hit stale Docker tag resolution before creating a cluster. The exact pinned existing IDs were rebound to their frozen names; Config/RootFS/IDs remained identical. A first loaded diagnostic was deliberately interrupted after source review found the completion marker after validation/close. Its 2,141 partial records were copied and verified before node cleanup and are excluded. The boundary was corrected in a separate code commit and the amendment resealed before the three accepted diagnostics. No timing/resource/acceptance choice used comparative outcomes.

Implementation commits: e32d192 (transport) and b3fd0d1 (frozen completion-boundary correctness). Focused tests: 19 passed. Full suite: 861 passed, 3 skipped. Tests cover all 18 frozen offer schedules, error stages, exact endpoint arithmetic, interrupted export recovery, duplicate/tamper rejection, interrupted generation, owner/restart refusal and old/new campaign exclusion.

The versioned restart-plan.json contains all 18 frozen cells in order, starting at slot 1, with zero old eligible runs and no automatic retries. It does not launch anything. The old dynapm ref, V8B evidence and scientific files are unchanged. Next work requires separate campaign execution authorization and the amended transport/provenance preflight; the old forwarding launcher is not eligible.
