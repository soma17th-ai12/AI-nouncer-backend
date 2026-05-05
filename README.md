# AI-nouncer · 한국어 발음 교정 데모 백엔드

사용자가 미리 정의된 한국어 문장을 읽으면 발음을 평가합니다. 
음성을 STT 로 받아 원문과 음절 단위로 비교합니다. 
불명확 후보를 추출한 뒤, Solar LLM 으로 다음 연습 방향을 제안합니다.

## 빠른 시작

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 를 열어 OPENAI_API_KEY, UPSTAGE_API_KEY 두 값을 채웁니다.

uvicorn app.main:app --reload --port 8000
```

## 환경 변수

`.env` 에 다음 두 값이 필요합니다.

| 키 | 용도 |
|---|---|
| `OPENAI_API_KEY` | Whisper STT (`whisper-1`, `language="ko"`) |
| `UPSTAGE_API_KEY` | Upstage Solar Pro 코칭 (`solar-pro`) |


## API

| 메서드 | 경로 | 입력 | 출력 |
|---|---|---|---|
| GET | `/healthz` | — | `{"status": "ok"}` |
| GET | `/api/v1/sentences` | — | `[{id, text}]` |
| POST | `/api/v1/analyze` | multipart: `audio` (file), `sentence_id` (str) | `{transcript, alignment, candidates, advice}` |

응답 예시:

```json
{
  "transcript": "삼촌은 신전한 생선을 사셨다",
  "alignment": [
    {"expected": "삼", "heard": "삼", "type": "match"},
    {"expected": "선", "heard": "전", "type": "ㅅ 계열 불명확"}
  ],
  "candidates": [
    {"index": 3, "expected": "선", "heard": "전", "type": "ㅅ 계열 불명확"}
  ],
  "advice": {
    "focus": "ㅅ 계열 발음에서 혀끝 위치가 살짝 안쪽으로 들어가는 듯합니다",
    "drills": ["'사-시-수-세-소' 5회 천천히", "'생선' 3회 후 '신선' 3회 교차 발음"]
  }
}
```

### 호출 예시

```bash
# 문장 풀 조회
curl -s http://localhost:8000/api/v1/sentences

# 음성 분석
curl -s -X POST http://localhost:8000/api/v1/analyze \
  -F "audio=@sample.webm;type=audio/webm" \
  -F "sentence_id=s1"
```

## 개발

```bash
# 자동 리로드 개발 서버
uvicorn app.main:app --reload --port 8000

# 단위 테스트 (aligner / detector)
pytest -v --tb=short
```

## 폴더 구조

```
.
├── app/
│   ├── main.py              # FastAPI 진입점, CORS, 라우터 등록
│   ├── config.py            # 환경변수 로드 (pydantic-settings)
│   ├── routers/
│   │   ├── sentences.py     # GET /api/v1/sentences
│   │   └── analyze.py       # POST /api/v1/analyze
│   ├── services/
│   │   ├── stt.py           # Whisper API 래퍼
│   │   ├── aligner.py       # 자모 분해 + Needleman-Wunsch 음절 정렬
│   │   ├── detector.py      # ㅅ 계열·종성 약화 후보 분류
│   │   └── coach.py         # Solar 코칭 프롬프트
│   ├── schemas/             # Pydantic 응답 스키마
│   └── data/sentences.json  # 미리 정의된 연습 문장
└── tests/                   # aligner / detector 단위 테스트
```

## 도메인 용어

- **음절 정렬**: 원문과 STT 결과를 한글 음절 단위로 전역 정렬한 결과. Needleman-Wunsch + 자모 거리(0~3).
- **자모 분해**: 한 음절을 (초성, 중성, 종성) 호환 자모로 분해.
- **ㅅ 계열 불명확**: 원문 초성이 ㅅ/ㅆ 인데 STT 초성이 다른 자음.
- **종성 약화**: 원문 종성이 있는데 같은 위치 STT 음절에 종성이 없음.
- **불명확 후보**: 위 패턴에 해당하는 음절. STT 오류와 발음 오류를 단정적으로 구분하지 않습니다.
