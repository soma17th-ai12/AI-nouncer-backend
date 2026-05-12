import json
import logging
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None

# 코칭 레퍼런스 라이브러리 로드
_LIBRARY_PATH = Path(__file__).parent.parent / "data" / "coaching_library.json"
_COACHING_LIBRARY: dict = json.loads(_LIBRARY_PATH.read_text(encoding="utf-8"))

_RULES = """\
규칙:
- "발음 오류"라고 단정하지 마세요. "불명확하게 들립니다", "살짝 약하게 들립니다" 같은 표현을 씁니다.
- 점수를 매기지 말고, 어느 부분을 어떻게 다시 읽을지를 안내합니다.
- 후보가 비어 있으면 격려와 함께 다음 단계 제안을 짧게 합니다.
- 위에 제시된 조음 메커니즘과 코칭 큐를 근거로만 피드백을 생성하세요.\
"""

_STEP1_SCHEMA = """\
응답은 반드시 다음 JSON 스키마만 출력합니다:
{
  "focus": "감지된 패턴에 근거한 한 문장 집중 포인트 (80자 이내)",
  "drills": ["조음 메커니즘 기반 구체적 연습 동작 2~4개 (각 50자 이내)"],
  "practice_words": ["감지된 패턴 음소가 풍부하게 포함된 한국어 단어 3~6개"]
}\
"""

_STEP2_SYSTEM = """\
당신은 한국어 발음 연습 문장 생성기입니다.
아래에 주어진 단어들을 최대한 많이 활용해서, 자연스럽고 짧은 한국어 문장을 하나 만드세요.

규칙:
- 문장은 30자 이내로 작성합니다.
- 주어진 단어 중 최소 2개 이상 포함해야 합니다.
- 어색하거나 억지스러운 표현은 피하세요.
- 응답은 반드시 다음 JSON 스키마만 출력합니다:
  {"next_sentence": "생성된 연습 문장"}\
"""

# Pydantic 응답 모델
class _Step1Response(BaseModel):
    focus: str
    drills: list[str]
    practice_words: list[str] = []

class _Step2Response(BaseModel):
    next_sentence: str

# Fallback 템플릿
_FALLBACK_STEP1: dict = {
    "focus": "발음을 다시 한 번 천천히 읽어보세요.",
    "drills": ["한 음절씩 끊어서 또렷하게 읽어보세요"],
    "practice_words": [],
}
_FALLBACK_STEP2: dict = {
    "next_sentence": "사슴 다섯 마리가 산을 달린다",
}


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://api.upstage.ai/v1/solar",
            api_key=settings.upstage_api_key,
        )
    return _client


def _call_with_retry(
    messages: list[dict],
    response_model: type[_Step1Response | _Step2Response],
    fallback: dict,
) -> dict:
    for attempt in range(2):
        try:
            resp = _get_client().chat.completions.create(
                model="solar-pro",
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw = json.loads(resp.choices[0].message.content)
            return response_model.model_validate(raw).model_dump()
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("Solar Pro 응답 검증 실패 (attempt %d/2): %s", attempt + 1, e)
            if attempt == 1:
                logger.error("재시도 후에도 실패 — fallback 반환")
                return fallback
    return fallback


def _build_step1_system(candidates: list[dict]) -> str:
    detected_types = {c["type"] for c in candidates if c["type"] in _COACHING_LIBRARY}

    if not detected_types:
        return f"""당신은 한국어 발음 코치입니다.

{_RULES}

{_STEP1_SCHEMA}"""

    ref_sections = []
    for pattern_type in detected_types:
        ref = _COACHING_LIBRARY[pattern_type]
        cues_text = "\n".join(f"  - {cue}" for cue in ref["cues"])
        ref_sections.append(
            f"패턴: {pattern_type}\n"
            f"  조음 메커니즘: {ref['mechanism']}\n"
            f"  코칭 큐:\n{cues_text}"
        )

    ref_block = "\n\n".join(ref_sections)

    return f"""당신은 한국어 발음 코치입니다.

[이번 세션 감지된 패턴 — 반드시 아래 메커니즘에 근거해서만 피드백하시오]
{ref_block}

{_RULES}

{_STEP1_SCHEMA}"""


def coach(expected: str, transcript: str, candidates: list[dict]) -> dict:
    # Step 1: 피드백 + 연습 단어 추출
    step1_system = _build_step1_system(candidates)
    payload = {
        "expected": expected,
        "transcript": transcript,
        "candidates": candidates,
    }
    step1 = _call_with_retry(
        messages=[
            {"role": "system", "content": step1_system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        response_model=_Step1Response,
        fallback=_FALLBACK_STEP1,
    )

    # Step 2: practice_words로 연습 문장 생성
    detected_types = list({c["type"] for c in candidates})
    step2_user = json.dumps(
        {"practice_words": step1.get("practice_words", []), "target_patterns": detected_types},
        ensure_ascii=False,
    )
    step2 = _call_with_retry(
        messages=[
            {"role": "system", "content": _STEP2_SYSTEM},
            {"role": "user", "content": step2_user},
        ],
        response_model=_Step2Response,
        fallback=_FALLBACK_STEP2,
    )

    return {**step1, **step2}
