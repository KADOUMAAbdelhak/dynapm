# Primary executor re-binding (boot 26051F76): strict preflight PASS

Binding-only re-binding commit **738139b** on `v8c5-service-transport` (parent 4c1326c). It changes only the current-boot certificate path, SHA-256 (b0d91ebc…), manifest, evidence commit (46a6869) and expected boot UUID (26051F76-7B84-4CBD-A25D-1418E39980A2) in `primary_observer_binding.py`, plus the amendment doc and two tests proving the superseded pre-reboot certificate (594ba9a2…, boot 6C470F9C) is rejected. The delta over observer 1b50282 is still exactly the five approved binding files; treatment code is AST-identical to 67bfd37; observer, transport, scientific source, limits and power criteria are unchanged.

Spec: `executor-spec-rebound.json` (SHA-256 d741b746c0ed13baf9fe2a058cc08c1370c0cbe31a0e59f403fe27bc89d17be9), derived by `make_spec.py` from the sealed binding spec f5d78b95…; only binding identity fields changed (asserted).

Tests: binding/observer/service focused suite 98 passed. Full suite 942 passed, 3 skipped, 53 errors — all 53 in the two Google-data test modules, which need `data/google2019` inside the frozen repo (that copy was removed with approval; the main repo keeps it). Unrelated to this binding.

Strict task50 preflight: PASS — source binding, host qualification (boot 26051F76, calendar discrepancy 53.3 ms), pinned images, engine isolation, storage (42.45 GB ≥ 28.02 GB) and the UUID power-guard window. Preflight SHA-256 65a0d393…. The protected 18-slot checkpoint 16c07107 is byte-identical; all 18 PENDING.

No cooldown, cluster, generator, 75-minute lifecycle, claim treatment or integration was started. Step B is gate-ready on a new root but NOT launched (`prepared-step-b-command.json`). Campaign v1 remains HALTED; campaign v2 not started.
