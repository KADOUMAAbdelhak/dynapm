"""Frozen positive, unambiguous request-history semantics; local operations only."""
import numpy as np
import pandas as pd

REQUEST_RULE = 'positive-unambiguous-request-history-v1'
KEYS = ['collection_id', 'instance_index', 'time']
PAIR = ['request_cpu', 'request_memory']


def prepare_request_history(events):
    frame = events[KEYS + PAIR].copy()
    numeric = frame.apply(pd.to_numeric, errors='coerce')
    good = np.isfinite(numeric.to_numpy(float)).all(axis=1) & numeric.request_cpu.gt(0) & numeric.request_memory.gt(0)
    positive = numeric.loc[good].copy()
    for col in KEYS:positive[col] = positive[col].astype('int64')
    for col in PAIR:positive[col] = positive[col].astype('float64')
    unique = positive.drop_duplicates(KEYS + PAIR)
    counts = unique.groupby(KEYS, sort=True).size().rename('distinct_request_pairs').reset_index()
    ambiguous = counts[counts.distinct_request_pairs.gt(1)].copy()
    tagged = unique.merge(counts, on=KEYS, validate='many_to_one')
    clean = tagged[tagged.distinct_request_pairs.eq(1)][KEYS+PAIR].sort_values(KEYS, kind='mergesort').reset_index(drop=True)
    latest = counts[KEYS].copy()
    latest['latest_ambiguous'] = counts.distinct_request_pairs.gt(1).to_numpy()
    diagnostics = dict(raw_event_rows=len(events), invalid_request_event_rows=int((~good).sum()),
        positive_event_rows=len(positive), identical_duplicate_copies=len(positive)-len(unique),
        distinct_request_tuples=len(unique), ambiguous_groups=len(ambiguous),
        ambiguous_distinct_request_tuples=int(ambiguous.distinct_request_pairs.sum()),
        usable_request_history_rows=len(clean), rule=REQUEST_RULE)
    return clean, ambiguous.reset_index(drop=True), latest, diagnostics
