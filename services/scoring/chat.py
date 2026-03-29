
from fastapi import APIRouter
from .schemas_chat import ChatRequest, ChatResponse
from .llm_service import llm_service
from .prompt_builder import build_messages

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    messages = build_messages(req.messages)

    response = llm_service.chat(
        messages=messages,
        temperature=req.temperature,
        top_p=req.top_p
    )

    return ChatResponse(response=response)