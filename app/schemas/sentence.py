from pydantic import BaseModel

class Sentence(BaseModel):
    id: str
    text: str
