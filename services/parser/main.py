import asyncio
import uvicorn
from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional

from core.logger import setup_logging
from core.config import SERVICES
from services.parser.service import ParserService

setup_logging(SERVICES['parser-service']['prefix'])

api = FastAPI(title=f"{SERVICES['parser-service']['prefix']} API")
app = api
router = APIRouter(tags=["parser-service"])
parser_service = ParserService()


class ParseRequest(BaseModel):
    user_id: str
    file_id: Optional[str] = None
    github_url: Optional[HttpUrl] = None
    youtube_url: Optional[HttpUrl] = None
    essay_text: Optional[str] = None


@router.post("/parse")
async def start_parsing(request: ParseRequest):
    if not request.file_id and not request.github_url and not request.youtube_url and not request.essay_text:
        raise HTTPException(
            status_code=422,
            detail="Provide file_id and/or github_url and/or youtube_url and/or essay_text",
        )

    try:
        return parser_service.queue_tasks(
            user_id=request.user_id,
            file_id=request.file_id,
            github_url=request.github_url,
            youtube_url=request.youtube_url,
            essay_text=request.essay_text,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/parse/tasks/{task_id}")
async def get_task_status(task_id: str):
    return parser_service.get_task_status(task_id)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "parser"}


api.include_router(router)


async def start_parser():
    print("[PARSER] parser-service ready")


async def main():
    cfg = SERVICES['parser-service']
    config = uvicorn.Config(
        api,
        host=cfg['url'],
        port=cfg['port'],
        log_level=cfg['log_level']
    )
    server = uvicorn.Server(config)
    await asyncio.gather(
        start_parser(),
        server.serve()
    )


if __name__ == "__main__":
    asyncio.run(main())
