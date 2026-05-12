"""
Coach 응답 품질 규칙 기반 pytest.
Solar Pro API를 mock하여 실제 API 호출 없이 실행됩니다.

항목별 배점 (7점 만점):
  1. 스키마 완전성      — focus, drills, practice_words, next_sentence 모두 존재
  2. focus 길이         — 80자 이내
  3. drills 개수        — 2~4개
  4. 레퍼런스 용어      — ㅅ계열 감지 시 focus에 "치조"/"혀끝"/"윗잇몸" 중 1개 이상
  5. practice_words 패턴— ㅅ계열 감지 시 ㅅ/ㅆ 초성 단어 ≥ 2개
  6. next_sentence 재사용— practice_words 중 ≥ 2개 포함
  7. next_sentence 길이  — 30자 이내
"""

import json
from unittest.mock import MagicMock, patch

import pytest

S_REF_TERMS = {"치조", "혀끝", "윗잇몸"}
S_INITIALS = ("ㅅ", "ㅆ")


def _has_s_initial(word: str) -> bool:
    """단어에 ㅅ/ㅆ 초성 음절이 하나 이상 있는지 확인."""
    try:
        from jamo import h2j
        for ch in word:
            if "가" <= ch <= "힣":
                code = ord(ch) - 0xAC00
                initial_idx = code // (21 * 28)
                initials = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
                if initial_idx < len(initials) and initials[initial_idx] in S_INITIALS:
                    return True
    except Exception:
        pass
    return False


def score_response(result: dict, candidates: list[dict]) -> tuple[int, list[str]]:
    """응답을 채점하고 (점수, 실패항목 목록) 반환."""
    score = 0
    failures = []
    s_detected = any(c.get("type") == "ㅅ 계열 불명확" for c in candidates)

    # 1. 스키마 완전성
    required = ["focus", "drills", "practice_words", "next_sentence"]
    if all(k in result for k in required):
        score += 1
    else:
        missing = [k for k in required if k not in result]
        failures.append(f"스키마 누락: {missing}")

    # 2. focus 길이
    if len(result.get("focus", "")) <= 80:
        score += 1
    else:
        failures.append(f"focus 길이 초과: {len(result['focus'])}자")

    # 3. drills 개수
    drills = result.get("drills", [])
    if 2 <= len(drills) <= 4:
        score += 1
    else:
        failures.append(f"drills 개수 오류: {len(drills)}개 (기대: 2~4)")

    # 4. 레퍼런스 용어 (ㅅ 계열 감지 시)
    if s_detected:
        focus = result.get("focus", "")
        if any(term in focus for term in S_REF_TERMS):
            score += 1
        else:
            failures.append(f"레퍼런스 용어 없음: focus='{focus[:30]}...'")
    else:
        score += 1  # 패턴 없으면 해당 없음 → 통과

    # 5. practice_words 패턴 일치 (ㅅ 계열 감지 시)
    words = result.get("practice_words", [])
    if s_detected:
        s_words = [w for w in words if _has_s_initial(w)]
        if len(s_words) >= 2:
            score += 1
        else:
            failures.append(f"ㅅ초성 단어 부족: {s_words} (≥2 필요)")
    else:
        score += 1

    # 6. next_sentence 단어 재사용
    next_s = result.get("next_sentence", "")
    reused = [w for w in words if w in next_s]
    if len(reused) >= 2:
        score += 1
    else:
        failures.append(f"단어 재사용 부족: {reused} (≥2 필요, next='{next_s}')")

    # 7. next_sentence 길이
    if len(next_s) <= 30:
        score += 1
    else:
        failures.append(f"next_sentence 길이 초과: {len(next_s)}자")

    return score, failures


# ── Fixtures ────────────────────────────────────────────────────────────────

MOCK_STEP1 = {
    "focus": "혀끝을 윗잇몸(치조) 바로 뒤에 위치시켜 '선'을 발음해보세요.",
    "drills": [
        "거울 앞에서 혀끝이 앞니에 닿지 않게 확인하며 발음",
        "스- 소리를 3초간 유지 후 선 발음",
    ],
    "practice_words": ["선물", "설날", "서울"],
}

MOCK_STEP2 = {"next_sentence": "설날 서울서 선물을 샀다"}

MOCK_STEP1_NO_CANDIDATE = {
    "focus": "전반적으로 명확하게 발음했습니다. 종성도 잘 유지됩니다.",
    "drills": [
        "이번 속도 그대로 한 번 더 읽어보세요",
        "조금 더 빠르게 읽어도 명확한지 시도해보세요",
    ],
    "practice_words": ["사슴", "산책"],
}

MOCK_STEP2_NO_CANDIDATE = {"next_sentence": "사슴이 산을 달린다"}


def _make_mock_response(content: dict):
    msg = MagicMock()
    msg.content = json.dumps(content, ensure_ascii=False)
    choice = MagicMock()
    choice.choices = [MagicMock(message=msg)]
    return choice


# ── Tests ────────────────────────────────────────────────────────────────────

@patch("app.services.coach._get_client")
def test_s_initial_candidate(mock_get_client):
    """ㅅ 계열 후보가 있을 때 레퍼런스 용어 + 패턴 단어 포함 여부 검증."""
    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_mock_response(MOCK_STEP1)
        return _make_mock_response(MOCK_STEP2)

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = side_effect
    mock_get_client.return_value = mock_client

    from app.services.coach import coach
    candidates = [{"index": 4, "expected": "선", "heard": "성", "type": "ㅅ 계열 불명확"}]
    result = coach("삼촌은 신선한 생선을 사셨다", "삼촌은 신성한 생선을 사셨다", candidates)

    sc, failures = score_response(result, candidates)
    assert sc >= 5, f"점수 {sc}/7 — 실패 항목: {failures}"


@patch("app.services.coach._get_client")
def test_no_candidate(mock_get_client):
    """후보 없을 때 기본 격려 응답 검증."""
    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_mock_response(MOCK_STEP1_NO_CANDIDATE)
        return _make_mock_response(MOCK_STEP2_NO_CANDIDATE)

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = side_effect
    mock_get_client.return_value = mock_client

    from app.services.coach import coach
    result = coach("사슴 다섯 마리가 산을 달린다", "사슴 다섯 마리가 산을 달린다", [])

    sc, failures = score_response(result, [])
    assert sc >= 5, f"점수 {sc}/7 — 실패 항목: {failures}"


@patch("app.services.coach._get_client")
def test_fallback_on_json_error(mock_get_client):
    """JSON 파싱 실패 시 fallback이 반환되는지 검증."""
    mock_client = MagicMock()
    bad_msg = MagicMock()
    bad_msg.content = "이건 JSON이 아닙니다"
    bad_choice = MagicMock()
    bad_choice.choices = [MagicMock(message=bad_msg)]
    mock_client.chat.completions.create.return_value = bad_choice
    mock_get_client.return_value = mock_client

    from app.services.coach import coach, _FALLBACK_STEP1, _FALLBACK_STEP2
    result = coach("삼촌은 신선한 생선을 사셨다", "삼촌은 신성한 생선을 사셨다",
                   [{"index": 4, "expected": "선", "heard": "성", "type": "ㅅ 계열 불명확"}])

    assert result["focus"] == _FALLBACK_STEP1["focus"]
    assert result["next_sentence"] == _FALLBACK_STEP2["next_sentence"]


@patch("app.services.coach._get_client")
def test_fallback_on_schema_error(mock_get_client):
    """필드 누락 시 fallback이 반환되는지 검증."""
    mock_client = MagicMock()
    bad_msg = MagicMock()
    bad_msg.content = json.dumps({"wrong_field": "엉뚱한 값"})
    bad_choice = MagicMock()
    bad_choice.choices = [MagicMock(message=bad_msg)]
    mock_client.chat.completions.create.return_value = bad_choice
    mock_get_client.return_value = mock_client

    from app.services.coach import coach, _FALLBACK_STEP1
    result = coach("삼촌은 신선한 생선을 사셨다", "삼촌은 신성한 생선을 사셨다",
                   [{"index": 4, "expected": "선", "heard": "성", "type": "ㅅ 계열 불명확"}])

    assert result["focus"] == _FALLBACK_STEP1["focus"]
