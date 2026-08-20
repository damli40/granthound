from granthound.store.models import FitAxes, FitScore, Verdict

WEIGHTS = {
    "eligibility": 0.30,
    "explicit_funding": 0.25,
    "effort_to_award": 0.20,
    "strategic": 0.15,
    "reliability": 0.10,
}

ELIGIBILITY_CAP = 2.0
APPLY_THRESHOLD = 3.5
WATCH_THRESHOLD = 2.5


def compute_fit_score(axes: FitAxes) -> FitScore:
    score = sum(getattr(axes, name) * weight for name, weight in WEIGHTS.items())
    capped = axes.eligibility == 0
    if capped:
        score = min(score, ELIGIBILITY_CAP)
    if score >= APPLY_THRESHOLD:
        verdict = Verdict.APPLY
    elif score >= WATCH_THRESHOLD:
        verdict = Verdict.WATCH
    else:
        verdict = Verdict.PASS
    return FitScore(score=round(score, 4), capped=capped, verdict_suggestion=verdict)
