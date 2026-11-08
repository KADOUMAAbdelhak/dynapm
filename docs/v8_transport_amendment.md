# V8C.4 additive transport observability amendment

Scientific source: fe3b870149a156e7fecb88741d51cfb5c1ed86d7.
Previous execution harness: d0ffc346e13d22f7b3d072fc59378831a668b3f2.
Original factual campaign evidence commit: 7bfe9a942ce362d10f6f133d64f29d2a87a0a5aa.

The new module is opt-in. No frozen source file, campaign attempt, treatment plan,
workload, endpoint definition, scientific input or original taxonomy is rewritten.
It is not automatically imported by the frozen campaign launcher. Campaign restart,
data-path redesign and acceptance/comparability review remain unauthorised here.

## Proven defects in the previous harness

The request worker maps OSError/URLError without a timeout reason to application_error,
and drops the exception type, errno, reason and stage. This mislabels transport failure
and prevents retrospective request-level attribution. A deadline is a recorded deadline,
but its cause is not established merely by classifying it as request_timeout.

The collector checks port-forward liveness approximately every five seconds, but the
main thread consumes a failed collector future only at a 300-second bucket boundary.
The load generator therefore keeps submitting requests after transport exits. The
original process return code/exit time and terminal cluster state are not preserved.
Original stdout/stderr are redirected to a regular file, not an unread PIPE: the code
does not support a pipe-buffer deadlock claim. There is one Popen, no automatic
port-forward restart, and no explicit request retry loop.

## Implemented opt-in changes

transport_observability.request_once preserves the same work URL, offered event,
5-second deadline and response success checks. It distinguishes an explicit HTTP
response, an ambiguous deadline and a definite connection/body-transport failure.
It records stage, exception reason chain, errno, response status and attempt number.
It does not turn a deadline into a successful or finite-completion outcome.

ProcessObserver records observed process status/signal and separates a live-scope
exit from requested cleanup. supervised_wait checks the guard and process at most
250 ms apart during a wait instead of deferring exit detection until a bucket closes.
No reconnect, retry, cancellation of accepted actuation or automatic replacement is
introduced. These primitives must be wired through a separately reviewed execution
harness before further claim measurements. They repair attribution and observation;
they do not claim to repair the underlying kubectl stream-collapse mechanism.

The forensic validity helper rejects definite transport loss, keeps uncertain timeout
causes unresolved, and does not reject a run solely for warning lines. Per-slot
historical assessments also use full request and Pod/cgroup timelines, not that helper
alone. A legacy record without exception details cannot be retroactively repaired.

## Review boundary

Independent Pod/status/cgroup enforcement remains valid evidence of resource actuation.
It does not establish application-path availability. The original COMPLETE status is an
executor terminal label and is preserved even when a subsequent scientific transport
review finds the primary application endpoints invalid.

No isolated exogenous slot-9 replacement is authorised or justified by this amendment:
multiple earlier cells have persistent stream-creation failures. Prospective measurement
path and comparability review are required. No diagnostic data may enter V8 endpoints.
