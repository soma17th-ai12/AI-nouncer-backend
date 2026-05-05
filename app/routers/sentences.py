import json
from pathlib import Path

from fastapi import APIRouter

from app.schemas.sentence import Sentence

router = APIRouter(tags=["sentences"])

_SENTENCES_PATH = Path(__file__).resolve().parent.parent / "data" / "sentences.json"
SENTENCES: list[Sentence] = [
    Sentence(**item) for item in json.loads(_SENTENCES_PATH.read_text(encoding="utf-8"))
]
BY_ID: dict[str, Sentence] = {s.id: s for s in SENTENCES}

@router.get("/sentences", response_model=list[Sentence])
def list_sentences() -> list[Sentence]:
    return SENTENCES
