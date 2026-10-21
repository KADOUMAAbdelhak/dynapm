# Materna exact-grid eligibility — causal-timeline-v3

This is a metadata-only audit, not model evaluation or a final cohort freeze.
The managed corrected pilot writes `materna_gap_eligibility_v3.parquet/json` for
all 1,576 retained entities, alongside the timestamp-only gap audit.

Training candidates are observed bootstrap targets after the initial 96 nominal
slots. Valid rows require finite paired history for all exact prior 96 slots
and an observed finite target. Each target-specific model also records its own
training validity. Gap-affected invalid rows exclude initial history warmup.

Streaming validity uses all available earlier bootstrap/stream observations.
Missing residual history pauses ADWIN, without reset. Long recovery periods
are contiguous invalid-origin runs of at least 96 nominal slots. Observation
windows are exact (t-24h,t] >=200 paired slots, and (t-6h,t] >=50 slots.
Hourly read opportunities are verifiable with >=200 exact forward slots and an
elapsed horizon, regardless of an observation at the read origin.

Per-period metadata maps each nominal tick to the first subsequent observed
common-eligible timestamp; ticks mapping to the same actual timestamp coalesce
to the latest nominal tick. It records immediate ticks, delayed commits, maximum
delay (latest represented tick), maximum wait of any due tick (including coalesced ticks) and unresolved ticks, without instantiating policies or predictors.

Diagnostic review flags identify zero training/evaluation opportunities or <95%
training/streaming/evaluation validity. This flag is NOT an exclusion rule and
changes no cohort. V2.5 must separately predefine final scientific eligibility.
Factual counts and corrected pilot identities will be added after verification.
