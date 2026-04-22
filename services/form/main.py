import asyncio
import json
import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from core.config import FORM_WORKFLOW_MAX_CONCURRENT_JOBS, SERVICES
from core.form_fields import normalize_form_payload
from core.logger import setup_logging
from core.network import normalize_bind_host
from core.orchestrator import Orchestrator, ServiceError
from services.form.service import FormService
from services.form.schemas.payload import FormSubmitRequest, FormSubmitResponse

setup_logging(SERVICES['form-service']['prefix'])
logger = logging.getLogger(__name__)

WORKFLOW_POLL_INTERVAL_SECONDS = 2.0
WORKFLOW_RETRY_DELAY_SECONDS = 30
WORKFLOW_TIMEOUT_SECONDS = 900
WORKFLOW_MAX_CONCURRENT_JOBS = max(1, FORM_WORKFLOW_MAX_CONCURRENT_JOBS)


def _build_stage_callback(response_id: int, job_id: int):
    def _callback(stage: str, status: str, detail: str | None = None) -> None:
        FormService.update_workflow_job_stage(job_id, stage)
        FormService.update_stage_status(
            response_id=response_id,
            stage=stage,
            status=status,
            error=str(detail)[:1000] if detail else None,
        )

    return _callback


async def _process_workflow_job(job: dict) -> None:
    response_id = int(job["response_id"])
    job_id = int(job["id"])
    raw_payload = json.loads(job["payload_json"])

    FormService.reset_response_stages(response_id)
    FormService.mark_response_processing(response_id)
    stage_callback = _build_stage_callback(response_id, job_id)

    try:
        await orchestrator.handle_form_submission(raw_payload, stage_callback=stage_callback)
    except Exception as exc:
        current_job = FormService.get_workflow_job(job_id) or {}
        current_stage = str(current_job.get("current_stage", "")).strip()
        error_text = str(exc)[:1000]
        if current_stage in {"parser", "scoring", "notification"}:
            FormService.update_stage_status(response_id, current_stage, "failed", error_text)
        failure = FormService.fail_workflow_job(
            job_id,
            str(exc),
            retry_delay_seconds=WORKFLOW_RETRY_DELAY_SECONDS,
        )
        final_status = str(failure.get("status", "retry")).lower()
        if final_status == "dead_letter":
            FormService.mark_response_failed(response_id, str(exc)[:1000])
        else:
            FormService.mark_response_pending(response_id)
        logger.exception(
            "Workflow job failed job_id=%s response_id=%s stage=%s status=%s attempts=%s/%s",
            job_id,
            response_id,
            current_stage or "workflow",
            final_status,
            current_job.get("attempts"),
            current_job.get("max_attempts"),
        )
        return

    FormService.mark_response_done(response_id)
    FormService.complete_workflow_job(job_id)
    logger.info("Workflow job completed job_id=%s response_id=%s", job_id, response_id)


async def _workflow_worker_loop() -> None:
    active_tasks: set[asyncio.Task[None]] = set()
    try:
        while True:
            while len(active_tasks) < WORKFLOW_MAX_CONCURRENT_JOBS:
                job = FormService.claim_next_workflow_job()
                if not job:
                    break
                active_tasks.add(asyncio.create_task(_process_workflow_job(job)))

            if not active_tasks:
                await asyncio.sleep(WORKFLOW_POLL_INTERVAL_SECONDS)
                continue

            done, pending = await asyncio.wait(
                active_tasks,
                timeout=WORKFLOW_POLL_INTERVAL_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                try:
                    task.result()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Workflow worker task crashed outside job handler")
            active_tasks = set(pending)
    except asyncio.CancelledError:
        for task in active_tasks:
            task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    recovered = FormService.recover_stale_workflow_jobs(timeout_seconds=WORKFLOW_TIMEOUT_SECONDS)
    if recovered:
        logger.warning("Recovered %s stale workflow jobs on startup", recovered)

    worker_task = asyncio.create_task(_workflow_worker_loop())
    app.state.workflow_worker_task = worker_task
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


api = FastAPI(title=f"{SERVICES['form-service']['prefix']} API", lifespan=lifespan)
router = APIRouter(tags=["form-service"])
orchestrator = Orchestrator()


@api.exception_handler(ServiceError)
async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": exc.detail})


# --- Routes ---
@router.post("/form-submit", response_model=FormSubmitResponse)
async def form_submit(payload: FormSubmitRequest):
    tg_id = payload.tg_id.strip()
    if not tg_id:
        return JSONResponse({"status": "error", "detail": "no tg_id"}, status_code=400)

    candidate = FormService.get_candidate(tg_id)
    if not candidate:
        return JSONResponse(
            {"status": "error", "detail": "candidate not found, start bot first"},
            status_code=404
        )

    raw_request = payload.model_dump()
    normalized_form_data = normalize_form_payload(raw_request)
    candidate_id = candidate["id"]
    workflow_payload = {
        "tg_id": tg_id,
        "candidate_id": str(candidate_id),
        **normalized_form_data,
    }
    response_id = FormService.save_response(candidate_id, workflow_payload)
    FormService.mark_response_pending(response_id)
    job_id = None
    try:
        job_id = FormService.enqueue_workflow_job(response_id, candidate_id, workflow_payload, max_attempts=3)
    except Exception as exc:
        FormService.mark_response_failed(response_id, str(exc)[:1000])
        raise HTTPException(
            status_code=500,
            detail=f"failed to enqueue workflow job: {exc}",
        ) from exc

    print(f"[FORM] accepted candidate_id={candidate_id} response_id={response_id} job_id={job_id} tg_id={tg_id}")
    return {
        "status": "accepted",
        "candidate_id": str(candidate_id),
        "response_id": int(response_id),
        "processing_status": "pending",
    }

@router.get("/health")
async def health():
    return {"status": "ok", "service": "form"}

# Include router in API
api.include_router(router)

# --- Entry point ---
async def main():
    cfg = SERVICES['form-service']
    config = uvicorn.Config(
        api,
        host=normalize_bind_host(str(cfg['url'])),
        port=cfg['port'],
        log_level=cfg['log_level']
    )
    server = uvicorn.Server(config)
    print(f"[FORM] starting api on :{cfg['port']}")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
