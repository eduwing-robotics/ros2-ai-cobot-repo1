from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class RuleResult:
    status: str
    names: List[str]
    expected: List[int]
    found: List[int]
    errors: List[str]

    @property
    def expected_total(self) -> int:
        return sum(self.expected)

    @property
    def found_total(self) -> int:
        return sum(self.found)

    @property
    def signature(self):
        return tuple(self.found), tuple(sorted(self.errors))


def _value(item, key):
    return item[key] if isinstance(item, dict) else getattr(item, key)


def evaluate_parts(
    observations: Iterable,
    catalog: Dict[str, dict],
    exact_count: bool = True,
    unknown_class: str = 'fail',
) -> RuleResult:
    names = list(catalog.keys())
    expected = [int(catalog[name]['expected']) for name in names]
    counts = {name: 0 for name in names}
    errors = []

    for item in observations:
        name = str(_value(item, 'name'))
        score = float(_value(item, 'score'))
        if name not in catalog:
            if unknown_class == 'fail':
                errors.append(f'UNKNOWN:{name}')
            continue
        minimum = float(catalog[name].get('min_score', 0.0))
        if score < minimum:
            errors.append(f'LOW_SCORE:{name}:{score:.2f}<{minimum:.2f}')
            continue
        counts[name] += 1

    found = [counts[name] for name in names]
    for name, wanted, actual in zip(names, expected, found):
        mismatch = actual != wanted if exact_count else actual < wanted
        if mismatch:
            errors.append(f'COUNT:{name}:{actual}/{wanted}')

    return RuleResult(
        status='PASS' if not errors else 'FAIL',
        names=names,
        expected=expected,
        found=found,
        errors=errors,
    )
