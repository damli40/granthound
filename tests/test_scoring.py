import pytest

from granthound.store.models import FitAxes, Verdict
from granthound.tools.scoring import WEIGHTS, compute_fit_score


def axes(**overrides):
    base = dict(eligibility=4, explicit_funding=4, effort_to_award=4, strategic=4, reliability=4)
    base.update(overrides)
    return FitAxes(**base)


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_perfect_axes_score_five_apply():
    r = compute_fit_score(axes(eligibility=5, explicit_funding=5, effort_to_award=5, strategic=5, reliability=5))
    assert r.score == pytest.approx(5.0)
    assert r.verdict_suggestion is Verdict.APPLY and r.capped is False


def test_eligibility_zero_caps_at_two_and_passes():
    r = compute_fit_score(axes(eligibility=0, explicit_funding=5, effort_to_award=5, strategic=5, reliability=5))
    assert r.score == pytest.approx(2.0)
    assert r.capped is True
    assert r.verdict_suggestion is Verdict.PASS


def test_threshold_boundaries():
    # weighted sum exactly 3.5 -> APPLY
    r = compute_fit_score(axes(eligibility=3.5, explicit_funding=3.5, effort_to_award=3.5, strategic=3.5, reliability=3.5))
    assert r.score == pytest.approx(3.5)
    assert r.verdict_suggestion is Verdict.APPLY
    # weighted sum 2.5 -> WATCH
    r = compute_fit_score(axes(eligibility=2.5, explicit_funding=2.5, effort_to_award=2.5, strategic=2.5, reliability=2.5))
    assert r.verdict_suggestion is Verdict.WATCH
    # below 2.5 -> PASS
    r = compute_fit_score(axes(eligibility=2, explicit_funding=2, effort_to_award=2, strategic=2, reliability=2))
    assert r.verdict_suggestion is Verdict.PASS


def test_fractional_axes_score_and_verdict_agree_at_boundary():
    r = compute_fit_score(FitAxes(eligibility=4.72, explicit_funding=3.17,
                                  effort_to_award=2.78, strategic=4.77, reliability=0.2))
    assert r.score == 3.5
    assert r.verdict_suggestion is Verdict.APPLY
