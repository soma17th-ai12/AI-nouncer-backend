from app.services.aligner import decompose

S_INITIALS = ("ㅅ", "ㅆ")

def _classify(expected: str, heard: str) -> str | None:
    if not expected or not heard:
        return None
    ce, _, te = decompose(expected)
    ch, _, th = decompose(heard)
    if ce in S_INITIALS and ch != ce:
        return "ㅅ 계열 불명확"
    if te and not th:
        return "종성 약화"
    return None


def detect_candidates(alignment: list[dict]) -> list[dict]:
    candidates: list[dict] = []
    for idx, item in enumerate(alignment):
        if item.get("type") != "sub":
            continue
        label = _classify(item["expected"], item["heard"])
        if label is None:
            continue
        item["type"] = label
        candidates.append(
            {
                "index": idx,
                "expected": item["expected"],
                "heard": item["heard"],
                "type": label,
            }
        )
    return candidates
