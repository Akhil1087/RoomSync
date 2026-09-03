WEIGHTS = {
    "budget": 20,
    "cleanliness": 20,
    "sleep": 20,
    "food": 15,
    "social": 15,
    "study": 10,
}


def _budget_score(a, b):
    amin, amax = a.budget_min or 0, a.budget_max or 0
    bmin, bmax = b.budget_min or 0, b.budget_max or 0
    if not all([amin, amax, bmin, bmax]):
        return 0.5
    overlap = max(0, min(amax, bmax) - max(amin, bmin))
    union = max(amax, bmax) - min(amin, bmin)
    return 1.0 if union == 0 else overlap / union


def _same(a, b, field):
    av, bv = getattr(a, field, ""), getattr(b, field, "")
    return 0.0 if not av or not bv else (1.0 if av == bv else 0.0)


def _clean_score(a, b):
    if not a.cleanliness_level or not b.cleanliness_level:
        return 0.5
    return max(0, 1 - abs(a.cleanliness_level - b.cleanliness_level) / 4)


def category_scores(a, b):
    return {
        "budget": _budget_score(a, b),
        "cleanliness": _clean_score(a, b),
        "sleep": _same(a, b, "sleep_schedule"),
        "food": _same(a, b, "food_habits"),
        "social": _same(a, b, "social_habits"),
        "study": _same(a, b, "study_habits"),
    }


def calculate_compatibility(a, b):
    scores = category_scores(a, b)
    total = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return round(total, 1), scores


def get_ranked_matches(current_student, students, pg_id=None):
    current = current_student.profile
    if not current:
        return []
    results = []
    for student in students:
        if student.id == current_student.id or not student.active or not student.profile:
            continue
        if pg_id is not None and (not student.profile.pg_flat_id or student.profile.pg_flat_id != pg_id):
            continue
        score, breakdown = calculate_compatibility(current, student.profile)
        results.append({"student": student, "score": score, "breakdown": breakdown})
    return sorted(results, key=lambda x: x["score"], reverse=True)
