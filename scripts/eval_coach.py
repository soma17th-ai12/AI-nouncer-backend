"""
Coach 응답 배치 품질 평가 스크립트.
실제 Solar Pro API를 호출하여 5개 샘플에 대한 품질 점수를 리포트합니다.

사용법:
    python scripts/eval_coach.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_coach_quality import score_response, SAMPLES  # type: ignore
from app.services.coach import coach

PASS_THRESHOLD = 5  # 7점 만점 중 5점 이상이면 통과


def run() -> None:
    print("\n=== Coach 응답 배치 품질 평가 ===\n")
    total_score = 0
    passed = 0

    for s in SAMPLES:
        result = coach(
            expected=s["expected"],
            transcript=s["transcript"],
            candidates=s["candidates"],
        )
        sc, failures = score_response(result, s["candidates"])
        total_score += sc
        ok = sc >= PASS_THRESHOLD
        passed += int(ok)
        mark = "✓" if ok else "✗"
        print(f"  {mark} [{s['label']:<14}]  {sc}/7점  focus: \"{result.get('focus', '')[:40]}...\"")
        for f in failures:
            print(f"       └ {f}")

    avg = total_score / len(SAMPLES)
    pass_rate = passed / len(SAMPLES) * 100
    print(f"""
─────────────────────────────────────────
평균 점수  : {avg:.1f}/7
통과 샘플  : {passed}/{len(SAMPLES)} ({pass_rate:.0f}%)
─────────────────────────────────────────
""")


if __name__ == "__main__":
    # SAMPLES를 scripts에서도 접근 가능하게 재정의
    SAMPLES = [
        {
            "label": "ㅅ계열 1개",
            "expected": "삼촌은 신선한 생선을 사셨다",
            "transcript": "삼촌은 신성한 생선을 사셨다",
            "candidates": [{"index": 4, "expected": "선", "heard": "성", "type": "ㅅ 계열 불명확"}],
        },
        {
            "label": "ㅅ계열 2개",
            "expected": "선생님은 시간 약속을 잘 지키셨다",
            "transcript": "전생님은 지간 약속을 잘 지키셨다",
            "candidates": [
                {"index": 0, "expected": "선", "heard": "전", "type": "ㅅ 계열 불명확"},
                {"index": 3, "expected": "시", "heard": "지", "type": "ㅅ 계열 불명확"},
            ],
        },
        {
            "label": "종성약화 1개",
            "expected": "솔직한 사람이 성공한다",
            "transcript": "솔지가 사라미 성공한다",
            "candidates": [{"index": 1, "expected": "직", "heard": "지", "type": "종성 약화"}],
        },
        {
            "label": "ㅅ+종성 혼합",
            "expected": "스승의 말씀은 평생 기억에 남습니다",
            "transcript": "으승의 말스는 평생 기억에 남스니다",
            "candidates": [
                {"index": 0, "expected": "스", "heard": "으", "type": "ㅅ 계열 불명확"},
                {"index": 2, "expected": "씀", "heard": "스", "type": "종성 약화"},
            ],
        },
        {
            "label": "후보없음 (완벽)",
            "expected": "사슴 다섯 마리가 산을 달린다",
            "transcript": "사슴 다섯 마리가 산을 달린다",
            "candidates": [],
        },
    ]
    run()
