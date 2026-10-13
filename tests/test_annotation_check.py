"""Benchmark sheet checker: agreement statistics."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_annotations import kappa  # noqa: E402


def test_kappa_perfect_and_chance():
    assert kappa([0, 1, 2, 3], [0, 1, 2, 3], "quadratic") == 1.0
    assert kappa([True, False, True, False], [True, False, True, False]) == 1.0
    # Cohen's classic example: po = 0.7, pe = 0.5 -> kappa = 0.4
    a = [1] * 50 + [0] * 50
    b = [1] * 35 + [0] * 15 + [1] * 15 + [0] * 35
    assert kappa(a, b) == pytest.approx(0.4)


def test_kappa_undefined_for_single_category():
    assert kappa([1, 1], [1, 1]) is None
