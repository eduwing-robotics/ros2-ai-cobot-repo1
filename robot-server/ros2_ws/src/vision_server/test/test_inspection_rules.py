from vision_server.inspection_rules import evaluate_parts
import pytest


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


@pytest.mark.parametrize('score', [float('nan'), float('inf'), -float('inf'), -.1, 1.1, None, 'bad'])
def test_invalid_scores_fail_and_are_not_counted(score):
    observations = complete_board()
    observations[0]['score'] = score
    result = evaluate_parts(observations, CATALOG)
    assert result.status == 'FAIL'
    assert result.found_total == 24
    assert 'INVALID_SCORE:gpu' in result.errors


def test_invalid_unknown_score_is_not_ignored():
    result = evaluate_parts(complete_board() + [{'name': 'unknown', 'score': float('nan')}],
                            CATALOG, unknown_class='ignore')
    assert result.status == 'FAIL'
