"""The accepted 1536 selection schema, also used by the portable verifier."""
STEP1 = [1396, 1393, 1391, 1388]
STEP2 = [1421, 1408, 1406, 1402]
RELOAD = 1387


def validate_selection(s):
    assert s['source_rows_measured'] == s['eligible_rows'] == 8000
    assert s['configured_max_length'] == 1536 and s['observed_max_length'] == 1421
    assert s['rows_above_limit'] == s['truncated_rows'] == 0
    assert s['optimizer_step_1_lengths'] == STEP1 and s['optimizer_step_2_lengths'] == STEP2
    assert s['selected_lengths'] == STEP1 + STEP2 and s['reload_length'] == RELOAD
    top = s['top9_by_length']
    assert len(top) == 9 and [r['rank'] for r in top] == list(range(1, 10))
    assert [r['length'] for r in top] == STEP2 + STEP1 + [RELOAD]
    assert top == sorted(top, key=lambda r: (-r['length'], r['id']))
    assert len({r['id'] for r in top}) == 9
    assert s['optimizer_step_1_ids'] == [r['id'] for r in top[4:8]]
    assert s['optimizer_step_2_ids'] == [r['id'] for r in top[:4]]
    assert s['selected_ids'] == s['optimizer_step_1_ids'] + s['optimizer_step_2_ids']
    assert s['reload_id'] == top[8]['id'] and s['reload_id'] not in s['selected_ids']
    assert s['all_length_max'] == s['observed_max_length']
    return True
