# V2.4B — Predictor Design Investigation

Status: implementation / managed execution pending. Development-only, not confirmation. Protocol remains `causal-timeline-v3`, evaluation `phase-balanced-hourly-v1`, accounting `refresh-accounting-v1`.

## Architecture audit and hypothesis

Production `VMPredictor` fits a one-step target-specific RF on bootstrap-only actual-history features. `predict_causal_horizon` repeatedly appends each predicted value, reconstructing all 96-slot causal rolling/lag/difference features, and predicts again. Calendar features remain deterministic. No future observation is read. CPU and memory models are independent.

This is temporally correct but creates a training/inference mismatch: every training feature uses actual utilization history, whereas recursive features increasingly contain model output. Trees return averages of observed training targets; rare spikes influence those averages, and altered rolling means/extrema/variance can lead subsequent predictions into different leaves. There is no stability or unbiasedness guarantee when this mapping is iterated 288 times. Frozen training support also prevents extrapolation to new regimes. Positive bias and reduced variation in V2.4 are evidence of this mechanism, not proof that every VM follows the same dynamics. We test removal of feedback, rather than assuming leakage or changing policy parameters.

## Predefined candidates — no search

1. Current RF recursion: 200 trees, depth20, sqrt features, seed42, one model thread; unchanged source.
2. Persistence: latest actual observation repeated for 288 slots.
3. Seasonal-naive 24h: exact actual value 288 nominal slots before each target, when available. Missing history remains unavailable; no fill or silent fallback.
4. Joint direct multi-output RF: same 200/depth20/sqrt/42 settings and first-target features, one tree ensemble per VM/resource with a 288-value response vector. Each output is predicted directly from the origin feature state, without feeding any prediction back. Shared splits capture cross-output dependence but do not guarantee a smooth path. No additional model family is justified in this bounded comparison.

Direct training uses complete exact-grid input history and all 288 finite labels within bootstrap. No training target crosses the bootstrap boundary; no gap bridging. Fewer direct training rows than one-step RF are expected and recorded; this is a deployment/data-cost property, not an invitation to use streaming labels. No training or inference on confirmatory entities. The investigation module is separate from production predictor/policy classes.

## Frozen execution and evaluation

Use the same 18 permanent development VMs and the same eight origins per VM as the provenance-validated V2.4 diagnosis. No new origin selection based on accuracy. Models fit once per resource/VM, then reuse their fit at all eight origins. All methods emit the same nominal `(t,t+24h]` target index; comparisons use identical observed finite target slots available to all four methods. Record incomplete seasonal forecasts explicitly. All 288 leads are retained, with selected summaries at 1/12/72/144/288.

Primary diagnostic endpoints are direct forecast MAE, signed bias, p95 of absolute point error, pointwise class correctness under frozen bootstrap thresholds, full error-vs-lead curves and per-VM heterogeneity. Mean-class/profile-p95 errors are supplementary diagnostics, not final profile-policy accuracy and not the selection target. Track adjacent predicted jumps relative to observed jumps as a descriptive consistency measure; smoothness alone is not forecast quality. No confirmatory tests or significance claims.

A new learned design cannot be recommended just for beating recursion: before seeing this run, require lower macro-VM full-horizon MAE than seasonal-naive for both CPU and memory, a strict majority of VM MAE wins in both resources, no worse absolute aggregate bias, causal/finite complete horizons and feasible costs. This is an exploratory design-screening rule, not a confirmatory practical-effect threshold. If it fails, do not tune/retry candidates to force a winner. A seasonal recommendation must also acknowledge required exact 24h source-history availability and unresolved deployment recovery behavior.

## Cost and provenance

Record bootstrap training time, each 288-target inference time, training-row count and tree node/value array bytes (a lower bound on model memory, not process peak RSS). Same machine/environment, at most two VM processes, one model thread each, no cross-run timing comparisons. Single measurements have no warm-up/repeat-controlled service benchmark claim. Simple controls need no fitting. All outputs are managed pilot-purpose artifacts under ignored `results/runs/`, with source/config/data/cohort/environment identities and hashed completion. Start only from a clean committed tree.

Machine-readable outputs: all forecast values/errors, per-origin metrics, per-VM metrics, all-lead curves, per-model/per-origin costs and summary JSON. The earlier diagnosis supplies only verified cohort/origin metadata, not forecasts reused as current output. Existing fitted models were not persisted; unchanged recursive RF models are refitted once per VM/resource.

## Gates

V2.4B must complete and be reviewed before V2.5. V2.5 and V3 remain blocked. No production integration occurs in this task, even if one candidate meets the screening rule. Integration, history-availability behavior, causal residual interfaces and policy revalidation require a separate task. No archive inputs, confirmatory outcomes, parameter tuning or model search are authorized.
