from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.routers.sentences import BY_ID
from app.schemas.analysis import Advice, AnalysisResponse
from app.services import aligner, audio_preprocess, coach, detector, stt

router = APIRouter(tags=["analyze"])

async def _evaluate(
    audio: UploadFile,
    expected: str,
    *,
    use_prompt: bool = False,
    denoise: bool = False,
    trim_silence: bool = False,
) -> AnalysisResponse:
    audio_bytes = await audio.read()
    processed_bytes, processed_name = audio_preprocess.preprocess(
        audio_bytes,
        audio.filename or "audio.webm",
        denoise=denoise,
        trim_silence=trim_silence,
    )
    prompt = stt.STT_PROMPT_NEUTRAL if use_prompt else None
    transcript = stt.transcribe(processed_bytes, filename=processed_name, prompt=prompt)
    alignment = aligner.align(expected, transcript)
    candidates = detector.detect_candidates(alignment)
    advice = coach.coach(expected, transcript, candidates)
    return AnalysisResponse(
        transcript=transcript,
        alignment=alignment,
        candidates=candidates,
        advice=Advice(**advice),
    )

def _resolve_sentence_text(sentence_id: str) -> str:
    sentence = BY_ID.get(sentence_id)
    if sentence is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 문장 ID 입니다.")
    return sentence.text

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    audio: UploadFile = File(...),
    sentence_id: str = Form(...),
) -> AnalysisResponse:
    return await _evaluate(audio, _resolve_sentence_text(sentence_id))

@router.post("/analyze/free", response_model=AnalysisResponse)
async def analyze_free(
    audio: UploadFile = File(...),
    sentence_text: str = Form(...),
) -> AnalysisResponse:
    expected = sentence_text.strip()
    if not expected:
        raise HTTPException(status_code=400, detail="문장이 비어 있습니다.")
    return await _evaluate(audio, expected)

@router.post("/analyze/full", response_model=AnalysisResponse)
async def analyze_full(
    audio: UploadFile = File(...),
    sentence_id: str = Form(...),
) -> AnalysisResponse:
    return await _evaluate(
        audio,
        _resolve_sentence_text(sentence_id),
        use_prompt=True,
        denoise=True,
        trim_silence=True,
    )

@router.post("/analyze/preprocess", response_model=AnalysisResponse)
async def analyze_preprocess(
    audio: UploadFile = File(...),
    sentence_id: str = Form(...),
) -> AnalysisResponse:
    return await _evaluate(
        audio,
        _resolve_sentence_text(sentence_id),
        denoise=True,
        trim_silence=True,
    )

@router.post("/analyze/prompt", response_model=AnalysisResponse)
async def analyze_prompt(
    audio: UploadFile = File(...),
    sentence_id: str = Form(...),
) -> AnalysisResponse:
    return await _evaluate(
        audio,
        _resolve_sentence_text(sentence_id),
        use_prompt=True,
    )

@router.post("/analyze/silence-only", response_model=AnalysisResponse)
async def analyze_silence_only(
    audio: UploadFile = File(...),
    sentence_id: str = Form(...),
) -> AnalysisResponse:
    return await _evaluate(
        audio,
        _resolve_sentence_text(sentence_id),
        trim_silence=True,
    )
