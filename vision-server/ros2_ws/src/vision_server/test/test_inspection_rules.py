from vision_server.inspection_rules import evaluate_parts


CATALOG = {
    'gpu': {'expected': 1, 'min_score': 0.60},
    'hbm': {'expected': 8, 'min_score': 0.55},
    'black_block': {'expected': 5, 'min_score': 0.55},
    'cap_small': {'expected': 5, 'min_score': 0.50},
    'marked_white': {'expected': 2, 'min_score': 0.55},
    'long_orange': {'expected': 4, 'min_score': 0.55},
}


def complete_board():
    return [
        {'name': name, 'score': 0.95}
        for name, settings in CATALOG.items()
        for _ in range(settings['expected'])
    ]


def test_complete_board_passes():
    result = evaluate_parts(complete_board(), CATALOG)
    assert result.status == 'PASS'
    assert result.expected_total == 25
    assert result.found_total == 25
    assert result.errors == []


def test_missing_hbm_fails():
    observations = complete_board()
    observations.pop(next(i for i, item in enumerate(observations) if item['name'] == 'hbm'))
    result = evaluate_parts(observations, CATALOG)
    assert result.status == 'FAIL'
    assert 'COUNT:hbm:7/8' in result.errors


def test_low_score_is_not_counted():
    observations = complete_board()
    next(item for item in observations if item['name'] == 'hbm')['score'] = 0.20
    result = evaluate_parts(observations, CATALOG)
    assert result.status == 'FAIL'
    assert any(error.startswith('LOW_SCORE:hbm:') for error in result.errors)
    assert 'COUNT:hbm:7/8' in result.errors


def test_unknown_class_fails():
    observations = complete_board() + [{'name': 'mystery', 'score': 0.99}]
    result = evaluate_parts(observations, CATALOG)
    assert result.status == 'FAIL'
    assert 'UNKNOWN:mystery' in result.errors
