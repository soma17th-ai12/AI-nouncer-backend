"""
Solar Pro JSON 스키마 준수율 측정 스크립트.

고정 입력 5개 × N회 반복으로 실제 API를 호출하고
JSON 파싱 성공률 / 스키마 완전성 / 길이 제약 준수율을 리포트합니다.

사용법:
    python scripts/measure_schema.py          # 기본 1회씩
    python scripts/measure_schema.py --repeat 3  # 각 샘플 3회 반복
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from openai import OpenAI

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

STEP1_REQUIRED = {"focus": str, "drills": list, "practice_words": list}
STEP2_REQUIRED = {"next_sentence": str}


def _get_client() -> OpenAI:
    return OpenAI(
        base_url="https://api.upstage.ai/v1/solar",
        api_key=settings.upstage_api_key,
    )


def _call(client: OpenAI, messages: list[dict]) -> tuple[bool, bool, dict | None]:
    """(json_ok, schema_ok, raw) 반환"""
    resp = client.chat.completions.create(
        model="solar-pro",
        messages=messages,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    try:
        raw = json.loads(content)
        return True, raw
    except json.JSONDecodeError:
        return False, None


def check_step1(raw: dict) -> dict[str, bool]:
    return {
        "schema": all(k in raw and isinstance(raw[k], t) for k, t in STEP1_REQUIRED.items()),
        "focus_len": len(raw.get("focus", "x" * 999)) <= 80,
        "drills_count": 2 <= len(raw.get("drills", [])) <= 4,
        "drills_len": all(len(d) <= 50 for d in raw.get("drills", [])),
    }


def check_step2(raw: dict) -> dict[str, bool]:
    return {
        "schema": all(k in raw and isinstance(raw[k], t) for k, t in STEP2_REQUIRED.items()),
        "sentence_len": len(raw.get("next_sentence", "x" * 999)) <= 30,
    }


def run(repeat: int) -> None:
    from app.services.coach import _build_step1_system, _STEP2_SYSTEM

    client = _get_client()
    total = len(SAMPLES) * repeat

    s1_json_ok = s1_schema_ok = s1_len_ok = 0
    s2_json_ok = s2_schema_ok = s2_len_ok = 0

    print(f"\n=== JSON 스키마 준수율 측정 (샘플 {len(SAMPLES)}개 × {repeat}회 = {total}회) ===\n")

    for r in range(repeat):
        for s in SAMPLES:
            label = f"[{s['label']} | run {r+1}]"

            # Step 1
            system1 = _build_step1_system(s["candidates"])
            payload = json.dumps(
                {"expected": s["expected"], "transcript": s["transcript"], "candidates": s["candidates"]},
                ensure_ascii=False,
            )
            json_ok, raw1 = _call(client, [{"role": "system", "content": system1}, {"role": "user", "content": payload}])
            s1_json_ok += int(json_ok)
            if json_ok:
                checks1 = check_step1(raw1)
                s1_schema_ok += int(checks1["schema"])
                s1_len_ok += int(checks1["focus_len"] and checks1["drills_count"] and checks1["drills_len"])
                status1 = "✓" if all(checks1.values()) else "△"
            else:
                status1 = "✗ JSON실패"

            # Step 2
            words = raw1.get("practice_words", []) if json_ok else []
            step2_user = json.dumps({"practice_words": words, "target_patterns": []}, ensure_ascii=False)
            json_ok2, raw2 = _call(client, [{"role": "system", "content": _STEP2_SYSTEM}, {"role": "user", "content": step2_user}])
            s2_json_ok += int(json_ok2)
            if json_ok2:
                checks2 = check_step2(raw2)
                s2_schema_ok += int(checks2["schema"])
                s2_len_ok += int(checks2["sentence_len"])
                status2 = "✓" if all(checks2.values()) else "△"
            else:
                status2 = "✗ JSON실패"

            print(f"  {label:<30}  Step1: {status1}  Step2: {status2}")

    def pct(n: int) -> str:
        return f"{n}/{total} ({n/total*100:.0f}%)"

    print(f"""
─────────────────────────────────────────
[Step 1] 총 {total}회
  JSON 파싱 성공   : {pct(s1_json_ok)}
  스키마 완전성    : {pct(s1_schema_ok)}
  길이 제약 준수   : {pct(s1_len_ok)}

[Step 2] 총 {total}회
  JSON 파싱 성공   : {pct(s2_json_ok)}
  스키마 완전성    : {pct(s2_schema_ok)}
  길이 제약 준수   : {pct(s2_len_ok)}

종합 스키마 준수율 : {(s1_schema_ok + s2_schema_ok) / (total * 2) * 100:.0f}%
─────────────────────────────────────────
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    run(args.repeat)
