# Google cell-g Stage-B replication

Stage B completed on the fixed held-out cell-g cohort. All 5,000 method–entity evaluations used the same 230,268 verified origins per method, for 1,151,340 scored records. The 1,000 selected entities came from 149,736 eligible entities. The fixed cohort had 468,641 nominal hourly origins, of which 230,268 were verifiable under protocol v2. The retained origins include 14,212 nominal reads without a same-time observation. Stage A and Stage B remain separate within-corpus estimates.

## Provenance and storage

- Source: `e34a4600edfd1d16e76b3a151871f42ed6c6dfd3`. Frozen protocol, staged design, secondary specification, staged inventory and both cohorts verified.
- Protocol v2 fingerprint: `88e11c165a05658fe587878a66ee2816f033957efceb883062b0577d4f98a2c1`. Staged design SHA-256: `dd857518fd7471a2e7c8cce94f6922f52aa278b637ff38f2656db807c322d33d`. Secondary spec SHA-256: `83a39740c9902c654512c24d1bc0e33f7e20544a0ef82964513294a5a5eee6e6`.
- g cohort SHA-256: `44f3bf4c14d6c708e58aa6f4280a4889b5bdcb3477a6b7053a35fd5ef84444e3`. e cohort SHA-256: `992210a9fa2dcf14926178bdb93291c6ebf4a9d0d5220df06742dee952baa39c`. e+g inventory SHA-256: `a97c7015efc9e033d4e01c71c221ed322d53015813ab7f977a86bf4407e9ca1a`.
- Primary fingerprint: `2906bbb683ed7fc46cddfb7eefa3d614efdda6e87b1e5c200cff9e98ee8dfdbf`. Run: `2026-11-06T230801.972546Z-2906bbb683ed-d622daf0`. Output manifest SHA-256: `04c52ef99141d397d96a05f646e286f0ec4808c4171df0434e4ff390024ffdf3`.
- Secondary fingerprint: `00644a34a152ed2d89e8e2b26ea1a27385f3aaad2d36d2b22a0d107865228cc9`. Run: `2026-11-07T001222.590845Z-00644a34a152-3f1fd13c`. Output manifest SHA-256: `5c5d570223b094049b5a8a923f64676111dc575bf3605e3931305f02020d507f`.
- Primary run-manifest SHA-256: `8bdf4736f0f12a2826e70de4680ff147899f5dc4a04201398b70e6d61f188ef6`. Secondary run-manifest SHA-256: `9e86667362d6cf21e237c1f6efc8a5cb0c8f6a3942229e0301d4774f6e7c7795`.
- Primary outputs: `results/runs/2906bbb683ed7fc46cddfb7eefa3d614efdda6e87b1e5c200cff9e98ee8dfdbf/2026-11-06T230801.972546Z-2906bbb683ed-d622daf0`. Secondary outputs: `results/google2019_collection_robustness/runs/00644a34a152ed2d89e8e2b26ea1a27385f3aaad2d36d2b22a0d107865228cc9/2026-11-07T001222.590845Z-00644a34a152-3f1fd13c`.
- Free space before execution / after verification and test-fixture cleanup: 22.64 GiB / 22.53 GiB. Prospective peak allowance: 1.72 GiB above the 20 GiB reserve.
- Four workers with one numeric-library thread each. The run environment records these resource settings. Primary managed elapsed time: 3,654.95 s. Secondary managed elapsed time: 23.10 s.
- All 256 canonical g shards, both sealed raw downloads (329,648 chunks), the e cohort, and the V8B ref and snapshot seal were verified. No cloud calls were made. The November ledger still records 449,979,620,664 processed bytes.

## Method summaries

Fidelity means weight each entity equally. Correctness is percent, MAE is in request-ratio units, and accounting columns are cohort totals. Initialization is excluded from runtime refreshes. Each runtime refresh writes four fields.

| Method | CPU correct % | Memory correct % | CPU p95 MAE | Memory p95 MAE | Init. | Runtime refreshes | Writes | Value changes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Static | 59.7342 | 41.5525 | 0.4586016 | 0.06112887 | 1,000 | 0 | 0 | 0 |
| PW-12h | 70.99381 | 61.69925 | 0.2938568 | 0.0534955 | 1,000 | 18,342 | 73,368 | 37,784 |
| PW-6h | 70.38763 | 63.38292 | 0.2946401 | 0.05553135 | 1,000 | 34,086 | 136,344 | 54,452 |
| PW-3h | 68.10792 | 63.63765 | 0.3119654 | 0.06609045 | 1,000 | 65,580 | 262,320 | 78,418 |
| Full-Rewrite | 72.22161 | 62.02491 | 0.2684135 | 0.05189436 | 1,000 | 2,749,147 | 10,996,588 | 731,675 |

## Frozen primary comparisons

Each contrast has 1,000 entity pairs. Effects are treatment minus control. Correctness differences are percentage points. Brackets give marginal 95% percentile paired-bootstrap intervals for means and medians (10,000 draws, seed 20251022). Wilcoxon is two-sided with zeros dropped. Holm uses the frozen F1/F2/F3 families of 15/10/5 tests. All entity-level differences are in the primary paired-effects Parquet file.

### PW-12h − Static

| Endpoint | Mean Δ [95% CI] | Median Δ [95% CI] | Wilcoxon p | Holm p | Nonzero pairs |
|---|---:|---:|---:|---:|---:|
| CPU correctness | 11.25961 [9.494942, 13.0673] | 0 [0, 0] | 1.10932e-22 | 6.655922e-22 | 676 |
| Memory correctness | 20.14676 [18.07127, 22.24636] | 6.243712 [2.897943, 10.06036] | 7.354999e-56 | 5.148499e-55 | 808 |
| CPU p95 MAE | -0.1647448 [-0.1850717, -0.144691] | -0.06099099 [-0.07956106, -0.03959765] | 1.869542e-65 | 2.243451e-64 | 1000 |
| Memory p95 MAE | -0.007633365 [-0.01128495, -0.003894727] | -0.003100689 [-0.004657996, -0.002125152] | 3.663042e-10 | 1.465217e-09 | 993 |
| Refresh events | 18.342 [17.31195, 19.332] | 9 [8, 9] | 8.822729e-166 | 1.323409e-164 | 1000 |

### PW-6h − Static

| Endpoint | Mean Δ [95% CI] | Median Δ [95% CI] | Wilcoxon p | Holm p | Nonzero pairs |
|---|---:|---:|---:|---:|---:|
| CPU correctness | 10.65342 [8.811522, 12.53628] | 0 [0, 0] | 3.728235e-18 | 1.864117e-17 | 735 |
| Memory correctness | 21.83043 [19.68639, 23.99828] | 9.307359 [4.761905, 13.28671] | 6.524243e-60 | 6.524243e-59 | 835 |
| CPU p95 MAE | -0.1639615 [-0.1847846, -0.1433101] | -0.0669168 [-0.08280265, -0.04424345] | 1.305454e-64 | 1.435999e-63 | 1000 |
| Memory p95 MAE | -0.005597513 [-0.009184483, -0.002114515] | -0.002953914 [-0.004126142, -0.001905292] | 1.495307e-06 | 2.990614e-06 | 993 |
| Refresh events | 34.086 [31.943, 36.14005] | 12 [11, 13] | 2.12916e-165 | 2.980824e-164 | 1000 |

### PW-3h − Static

| Endpoint | Mean Δ [95% CI] | Median Δ [95% CI] | Wilcoxon p | Holm p | Nonzero pairs |
|---|---:|---:|---:|---:|---:|
| CPU correctness | 8.373718 [6.41047, 10.32715] | 0 [0, 0] | 5.137298e-10 | 1.541189e-09 | 782 |
| Memory correctness | 22.08516 [19.86567, 24.29741] | 11.22821 [6.818182, 16.70081] | 2.343581e-59 | 2.109223e-58 | 855 |
| CPU p95 MAE | -0.1466362 [-0.1681622, -0.1253672] | -0.05091031 [-0.07286802, -0.03600992] | 6.908933e-59 | 5.527146e-58 | 1000 |
| Memory p95 MAE | 0.004961583 [0.0004529575, 0.009495019] | -0.001447083 [-0.002609776, -0.0006979104] | 0.822794 | 0.822794 | 993 |
| Refresh events | 65.58 [61.19995, 69.78118] | 19 [18, 21] | 2.992317e-165 | 3.890012e-164 | 1000 |

### PW-6h − PW-12h

| Endpoint | Mean Δ [95% CI] | Median Δ [95% CI] | Wilcoxon p | Holm p | Nonzero pairs |
|---|---:|---:|---:|---:|---:|
| CPU correctness | -0.6061863 [-1.114597, -0.144298] | 0 [0, 0] | 2.546225e-05 | 0.000101849 | 455 |
| Memory correctness | 1.68367 [1.013788, 2.405267] | 0 [0, 0] | 1.983769e-12 | 1.587015e-11 | 470 |
| CPU p95 MAE | 0.0007832562 [-0.003339689, 0.005028665] | -0.0004646947 [-0.0007119468, -0.0002633508] | 4.554917e-06 | 2.277459e-05 | 988 |
| Memory p95 MAE | 0.002035852 [-0.0005337259, 0.004003949] | -0.0001951778 [-0.0002803634, -6.808796e-05] | 0.4333617 | 0.4333617 | 978 |
| Refresh events | 15.744 [14.61198, 16.82203] | 4 [3, 4] | 9.216265e-154 | 8.294638e-153 | 926 |

### PW-3h − PW-6h

| Endpoint | Mean Δ [95% CI] | Median Δ [95% CI] | Wilcoxon p | Holm p | Nonzero pairs |
|---|---:|---:|---:|---:|---:|
| CPU correctness | -2.279706 [-3.053519, -1.541742] | 0 [0, 0] | 0.01886465 | 0.03772929 | 525 |
| Memory correctness | 0.2547289 [-0.5060698, 1.020319] | 0 [0, 0] | 9.820761e-07 | 5.892457e-06 | 491 |
| CPU p95 MAE | 0.01732534 [0.01043962, 0.02450911] | -0.0004303383 [-0.0005948245, -0.0002507591] | 0.005451933 | 0.0163558 | 996 |
| Memory p95 MAE | 0.0105591 [0.008203322, 0.0133133] | -2.118096e-05 [-6.983351e-05, 0] | 3.133588e-09 | 2.193512e-08 | 983 |
| Refresh events | 31.494 [29.23697, 33.63403] | 7 [6, 8] | 9.972125e-164 | 9.972125e-163 | 990 |

### Full-Rewrite − PW-3h

| Endpoint | Mean Δ [95% CI] | Median Δ [95% CI] | Wilcoxon p | Holm p | Nonzero pairs |
|---|---:|---:|---:|---:|---:|
| CPU correctness | 4.113687 [3.282124, 4.95863] | 0.4246361 [0.2481263, 0.6036217] | 5.583798e-35 | 1.11676e-34 | 701 |
| Memory correctness | -1.612746 [-2.550844, -0.7165891] | 0 [0, 0] | 0.05821883 | 0.05821883 | 686 |
| CPU p95 MAE | -0.04355195 [-0.05211663, -0.03556801] | -0.00118744 [-0.001975582, -0.0008770212] | 3.487125e-44 | 1.39485e-43 | 999 |
| Memory p95 MAE | -0.01419609 [-0.01783062, -0.01090916] | -0.000434535 [-0.0005955374, -0.0003356116] | 1.288803e-39 | 3.866409e-39 | 989 |
| Refresh events | 2683.567 [2538.452, 2824.523] | 1362 [1205.5, 1611] | 3.021866e-165 | 1.510933e-164 | 1000 |

Across the 30 tests, 27 Holm-adjusted p-values are below .05. PW-12h and PW-6h improve all four mean fidelity endpoints versus Static in both cells. In g, PW-3h improves both mean correctness endpoints and mean CPU MAE versus Static. Its mean memory MAE increases by 0.004962, while its median paired memory MAE decreases by 0.001447 and the Wilcoxon p-value is 0.823. The mean, median and rank-based results describe different aspects of the paired distribution.

## Collection-aware secondary sensitivity

The 1,000 entities span 182 collections, including 82 singletons. Collection size min/median/max is 1/2/35. Top-1/3/5 shares are 3.5%/9.2%/13.7%. HHI is 0.014324 and inverse HHI is 69.813. Inverse HHI describes concentration.

Size histogram (size: number of collections): 1: 82, 2: 27, 3: 11, 4: 4, 5: 7, 6: 2, 7: 3, 8: 2, 9: 2, 10: 2, 11: 1, 12: 6, 13: 3, 14: 5, 15: 2, 16: 4, 17: 2, 18: 2, 19: 4, 20: 4, 22: 3, 23: 1, 24: 1, 33: 1, 35: 1.

Each interval below resamples whole collections with replacement (10,000 draws, seed 20251022). The entity mean column keeps the primary point estimate and uses collection-based uncertainty. The other columns use equal collection weights. Sign counts refer to within-collection means.

| Contrast | Endpoint | Entity mean [95% CI] | Equal-collection mean [95% CI] | Collection median of means [95% CI] | Positive / zero / negative |
|---|---|---:|---:|---:|---:|
| PW-12h − Static | CPU correctness | 11.25961 [8.827714, 14.03764] | 19.71666 [15.85653, 23.64246] | 11.32912 [8.292378, 14.42776] | 138 / 2 / 42 |
| PW-12h − Static | Memory correctness | 20.14676 [14.95295, 25.81118] | 32.93966 [28.47125, 37.34882] | 33.31035 [28.29787, 37.22634] | 148 / 1 / 33 |
| PW-12h − Static | CPU p95 MAE | -0.1647448 [-0.2136562, -0.1149423] | -0.08157846 [-0.1111168, -0.05709929] | -0.01769139 [-0.02696871, -0.01135037] | 32 / 0 / 150 |
| PW-12h − Static | Memory p95 MAE | -0.007633365 [-0.01552125, -0.0005542101] | -0.02250283 [-0.03230859, -0.01457682] | -0.008421589 [-0.01201521, -0.005117745] | 35 / 0 / 147 |
| PW-12h − Static | Refresh events | 18.342 [15.2739, 22.00547] | 30.90418 [28.6261, 33.02508] | 39.73077 [35, 42.58333] | 182 / 0 / 0 |
| PW-6h − Static | CPU correctness | 10.65342 [8.085721, 13.67112] | 20.6302 [16.69866, 24.56734] | 11.74317 [8.068349, 16.27149] | 138 / 3 / 41 |
| PW-6h − Static | Memory correctness | 21.83043 [16.20339, 27.90476] | 34.74644 [30.32924, 39.07853] | 34.45307 [30.23158, 40.72475] | 150 / 1 / 31 |
| PW-6h − Static | CPU p95 MAE | -0.1639615 [-0.2137223, -0.1132023] | -0.08322157 [-0.1144136, -0.05782061] | -0.01871988 [-0.02896636, -0.01154776] | 30 / 0 / 152 |
| PW-6h − Static | Memory p95 MAE | -0.005597513 [-0.01347155, 0.001403193] | -0.02256462 [-0.03252223, -0.01449263] | -0.009066457 [-0.01246936, -0.005715553] | 29 / 0 / 153 |
| PW-6h − Static | Refresh events | 34.086 [27.60535, 41.82288] | 60.82112 [56.07884, 65.2301] | 79.5 [70, 84.75] | 182 / 0 / 0 |
| PW-3h − Static | CPU correctness | 8.373718 [5.585496, 11.71836] | 20.6757 [16.65788, 24.68963] | 12.50236 [7.224785, 18.10843] | 129 / 3 / 50 |
| PW-3h − Static | Memory correctness | 22.08516 [16.22031, 28.34875] | 35.40968 [30.93134, 39.80127] | 35.66398 [31.58954, 40.97996] | 151 / 1 / 30 |
| PW-3h − Static | CPU p95 MAE | -0.1466362 [-0.1946564, -0.09767332] | -0.07933691 [-0.1108589, -0.05405379] | -0.01777787 [-0.02900428, -0.01057388] | 31 / 0 / 151 |
| PW-3h − Static | Memory p95 MAE | 0.004961583 [-0.003532618, 0.01257231] | -0.01967948 [-0.02989141, -0.01133685] | -0.00595909 [-0.009844742, -0.004252394] | 34 / 0 / 148 |
| PW-3h − Static | Refresh events | 65.58 [52.29176, 81.43367] | 120.4206 [110.8094, 129.3589] | 159.25 [139, 168] | 182 / 0 / 0 |
| PW-6h − PW-12h | CPU correctness | -0.6061863 [-1.15221, -0.03422715] | 0.9135433 [0.5053682, 1.296317] | 1.190172 [0.8032089, 1.209076] | 116 / 21 / 45 |
| PW-6h − PW-12h | Memory correctness | 1.68367 [0.7450337, 2.815123] | 1.806789 [1.365083, 2.307785] | 1.414141 [0.9919746, 1.810865] | 130 / 11 / 41 |
| PW-6h − PW-12h | CPU p95 MAE | 0.0007832562 [-0.003192294, 0.004628748] | -0.001643109 [-0.004075029, 0.0005642091] | -0.0005561781 [-0.0008493972, -0.000409519] | 42 / 0 / 140 |
| PW-6h − PW-12h | Memory p95 MAE | 0.002035852 [-0.0003383306, 0.003874796] | -6.178978e-05 [-0.0007487952, 0.0005916926] | -0.0003987627 [-0.0005175783, -0.0003072108] | 40 / 0 / 142 |
| PW-6h − PW-12h | Refresh events | 15.744 [12.33008, 19.80218] | 29.91694 [27.45808, 32.21085] | 40 [35, 42] | 182 / 0 / 0 |
| PW-3h − PW-6h | CPU correctness | -2.279706 [-3.164791, -1.331238] | 0.04550049 [-0.4012894, 0.4610724] | 0.7625969 [0.6036217, 1.006036] | 118 / 15 / 49 |
| PW-3h − PW-6h | Memory correctness | 0.2547289 [-0.486869, 1.159904] | 0.6632377 [0.3523129, 1.014948] | 0.6036217 [0.4024145, 0.8465033] | 125 / 17 / 40 |
| PW-3h − PW-6h | CPU p95 MAE | 0.01732534 [0.009004147, 0.02645832] | 0.003884652 [0.0006223166, 0.007531556] | -0.0004159879 [-0.0005530983, -0.0002356487] | 43 / 0 / 139 |
| PW-3h − PW-6h | Memory p95 MAE | 0.0105591 [0.007583151, 0.01348133] | 0.002885142 [0.001754944, 0.004165674] | -0.0002125994 [-0.0002834014, -0.0001635584] | 43 / 0 / 139 |
| PW-3h − PW-6h | Refresh events | 31.494 [24.69121, 39.60338] | 59.59943 [54.69896, 64.12585] | 79 [69.4375, 83] | 182 / 0 / 0 |
| Full-Rewrite − PW-3h | CPU correctness | 4.113687 [3.224074, 4.987454] | 1.846567 [1.460867, 2.275015] | 0.9729395 [0.804829, 1.207243] | 159 / 7 / 16 |
| Full-Rewrite − PW-3h | Memory correctness | -1.612746 [-3.063264, -0.27403] | -0.07883675 [-0.6314323, 0.400798] | 0.6048412 [0.4640849, 0.8002925] | 130 / 17 / 35 |
| Full-Rewrite − PW-3h | CPU p95 MAE | -0.04355195 [-0.05599303, -0.03112785] | -0.01542032 [-0.02092706, -0.0104393] | -0.0007339526 [-0.001003273, -0.0005471972] | 11 / 0 / 171 |
| Full-Rewrite − PW-3h | Memory p95 MAE | -0.01419609 [-0.01785712, -0.0103205] | -0.004725119 [-0.006298057, -0.00332162] | -0.000335925 [-0.0004221567, -0.0002617196] | 8 / 0 / 174 |
| Full-Rewrite − PW-3h | Refresh events | 2683.567 [2258.801, 3195.911] | 4406.942 [4092.061, 4699.73] | 5628.5 [4963, 6037.5] | 182 / 0 / 0 |

Entity weighting and equal collection weighting agree on the direction of 25 of the 30 point estimates. In the other five, the point estimates have opposite signs. For PW-3h versus Static, the memory MAE mean is +0.004962 with entity weighting and −0.01968 with equal collection weighting. The whole-collection interval for the entity mean spans zero. Overall, 25 entity-mean whole-collection intervals exclude zero. Those intervals are marginal secondary estimates.

## Descriptive replication against Stage A

These labels summarize separate primary mean estimates. An interval containing zero yields inconclusive. Opposite signs with both intervals excluding zero yield reversed. Same-direction overlapping intervals yield directionally replicated. For same-direction disjoint intervals, the magnitude of the g point estimate determines attenuated or amplified. Interval overlap is used only to label descriptive patterns.

| Contrast | Endpoint | e mean [95% CI] | g mean [95% CI] | Descriptive classification |
|---|---|---:|---:|---|
| PW-12h − Static | CPU correctness | 9.51636 [8.124721, 10.92757] | 11.25961 [9.494942, 13.0673] | Directionally replicated |
| PW-12h − Static | Memory correctness | 30.43949 [28.51781, 32.40527] | 20.14676 [18.07127, 22.24636] | Attenuated |
| PW-12h − Static | CPU p95 MAE | -0.009408147 [-0.01132961, -0.007509564] | -0.1647448 [-0.1850717, -0.144691] | Amplified |
| PW-12h − Static | Memory p95 MAE | -0.01228214 [-0.01404464, -0.01073602] | -0.007633365 [-0.01128495, -0.003894727] | Directionally replicated |
| PW-12h − Static | Refresh events | 34.563 [33.90297, 35.21603] | 18.342 [17.31195, 19.332] | Attenuated |
| PW-6h − Static | CPU correctness | 10.80813 [9.424416, 12.20903] | 10.65342 [8.811522, 12.53628] | Directionally replicated |
| PW-6h − Static | Memory correctness | 31.90214 [29.98759, 33.86406] | 21.83043 [19.68639, 23.99828] | Attenuated |
| PW-6h − Static | CPU p95 MAE | -0.01063785 [-0.01253808, -0.008780398] | -0.1639615 [-0.1847846, -0.1433101] | Amplified |
| PW-6h − Static | Memory p95 MAE | -0.0132817 [-0.01503206, -0.01174808] | -0.005597513 [-0.009184483, -0.002114515] | Attenuated |
| PW-6h − Static | Refresh events | 68.888 [67.58498, 70.17108] | 34.086 [31.943, 36.14005] | Attenuated |
| PW-3h − Static | CPU correctness | 11.71163 [10.3335, 13.10193] | 8.373718 [6.41047, 10.32715] | Attenuated |
| PW-3h − Static | Memory correctness | 32.80785 [30.89551, 34.78024] | 22.08516 [19.86567, 24.29741] | Attenuated |
| PW-3h − Static | CPU p95 MAE | -0.01149313 [-0.01342322, -0.009633673] | -0.1466362 [-0.1681622, -0.1253672] | Amplified |
| PW-3h − Static | Memory p95 MAE | -0.01382851 [-0.01557611, -0.01228633] | 0.004961583 [0.0004529575, 0.009495019] | Reversed |
| PW-3h − Static | Refresh events | 137.056 [134.47, 139.616] | 65.58 [61.19995, 69.78118] | Attenuated |
| PW-6h − PW-12h | CPU correctness | 1.291772 [1.091774, 1.490935] | -0.6061863 [-1.114597, -0.144298] | Reversed |
| PW-6h − PW-12h | Memory correctness | 1.462645 [1.275894, 1.646462] | 1.68367 [1.013788, 2.405267] | Directionally replicated |
| PW-6h − PW-12h | CPU p95 MAE | -0.001229707 [-0.001521186, -0.0009403432] | 0.0007832562 [-0.003339689, 0.005028665] | Inconclusive |
| PW-6h − PW-12h | Memory p95 MAE | -0.0009995633 [-0.001104536, -0.0008968286] | 0.002035852 [-0.0005337259, 0.004003949] | Inconclusive |
| PW-6h − PW-12h | Refresh events | 34.325 [33.68, 34.962] | 15.744 [14.61198, 16.82203] | Attenuated |
| PW-3h − PW-6h | CPU correctness | 0.9035006 [0.7929792, 1.014016] | -2.279706 [-3.053519, -1.541742] | Reversed |
| PW-3h − PW-6h | Memory correctness | 0.9057141 [0.8191983, 0.993326] | 0.2547289 [-0.5060698, 1.020319] | Inconclusive |
| PW-3h − PW-6h | CPU p95 MAE | -0.0008552744 [-0.00103639, -0.0006798113] | 0.01732534 [0.01043962, 0.02450911] | Reversed |
| PW-3h − PW-6h | Memory p95 MAE | -0.0005468046 [-0.0006203188, -0.0004743497] | 0.0105591 [0.008203322, 0.0133133] | Reversed |
| PW-3h − PW-6h | Refresh events | 68.168 [66.87798, 69.44602] | 31.494 [29.23697, 33.63403] | Attenuated |
| Full-Rewrite − PW-3h | CPU correctness | 0.812019 [0.7355159, 0.8904729] | 4.113687 [3.282124, 4.95863] | Amplified |
| Full-Rewrite − PW-3h | Memory correctness | 0.8366093 [0.7658259, 0.9061863] | -1.612746 [-2.550844, -0.7165891] | Reversed |
| Full-Rewrite − PW-3h | CPU p95 MAE | -0.0008884206 [-0.001028657, -0.0007537975] | -0.04355195 [-0.05211663, -0.03556801] | Amplified |
| Full-Rewrite − PW-3h | Memory p95 MAE | -0.0005180767 [-0.0005746167, -0.000460836] | -0.01419609 [-0.01783062, -0.01090916] | Amplified |
| Full-Rewrite − PW-3h | Refresh events | 4904.029 [4811.839, 4995.053] | 2683.567 [2538.452, 2824.523] | Attenuated |

The 30 descriptive labels are 4 directionally replicated, 11 attenuated, 6 amplified, 6 reversed and 3 inconclusive. Stage A and Stage B jointly support a within-corpus replication of mean fidelity gains for PW-12h and PW-6h versus Static, alongside higher refresh costs. The cadence effects vary by resource and endpoint. For example, both CPU correctness increments reverse in g, and PW-3h versus PW-6h has higher mean CPU and memory MAE in g. Report the two cells separately. Operational benefit and practical superiority require separate evidence.

## Verification

Both g output manifests and all declared file hashes passed managed cache validation. Independent checks reconstructed all scored-origin and refresh counts, 30,000 paired deltas, 30 primary bootstrap and Wilcoxon/Holm results, and 30 sets of collection bootstrap intervals. Initialization and runtime accounting reconcile separately.

Full suite after isolating the missing-g-binding test in a fixture: **828 passed, 1 skipped**. The first sandboxed test pass also lacked the local HTTP and hardware metadata access used by unrelated tests. The host-access rerun passed. The test-only change was made after both scientific runs sealed.
