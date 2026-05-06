from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.routers.sentences import BY_ID
from app.schemas.analysis import Advice, AnalysisResponse
from app.services import aligner, coach, detector, stt

router = APIRouter(tags=["analyze"])


async def _evaluate(audio: UploadFile, expected: str) -> AnalysisResponse:
    audio_bytes = await audio.read()
    transcript = stt.transcribe(audio_bytes, filename=audio.filename or "audio.webm")
    alignment = aligner.align(expected, transcript)
    candidates = detector.detect_candidates(alignment)
    advice = coach.coach(expected, transcript, candidates)
    return AnalysisResponse(
        transcript=transcript,
        alignment=alignment,
        candidates=candidates,
        advice=Advice(**advice),
    )


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    audio: UploadFile = File(...),
    sentence_id: str = Form(...),
) -> AnalysisResponse:
    sentence = BY_ID.get(sentence_id)
    if sentence is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 문장 ID 입니다.")
    return await _evaluate(audio, sentence.text)


@router.post("/analyze/free", response_model=AnalysisResponse)
async def analyze_free(
    audio: UploadFile = File(...),
    sentence_text: str = Form(...),
) -> AnalysisResponse:
    expected = sentence_text.strip()
    if not expected:
        raise HTTPException(status_code=400, detail="문장이 비어 있습니다.")
    return await _evaluate(audio, expected)
