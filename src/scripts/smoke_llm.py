# scripts/smoke_llm.py
import asyncio
from pydantic import BaseModel
from src.llm.openai import get_llm
from src.llm.base   import Message

class TestOutput(BaseModel):
    answer: str
    confidence: float

async def main() -> None:
    llm = get_llm()
    result = await llm.complete(
        messages=[Message("user", "What is 2+2? Return JSON.")],
        response_model=TestOutput,
    )
    print(result)

asyncio.run(main())