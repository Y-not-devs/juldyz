import asyncio
from core.gateway import app as gateway_app
from core.celery_app import celery
from shared.redis_client import redis_client
import uvicorn

async def start_gateway():
    """
    Start the FastAPI gateway.
    """
    print("[MAIN] Starting gateway...")
    config = {"host": "0.0.0.0", "port": 8000, "log_level": "info"}
    uvicorn.run(gateway_app, **config)

async def start_celery_worker():
    """
    Start Celery worker.
    """
    print("[MAIN] Starting Celery worker...")
    from celery.bin.worker import worker
    worker_app = worker(app=celery)
    worker_app.run(loglevel="info")

async def main():
    """
    Main entry point for the application.
    """
    print("[MAIN] Initializing Redis...")
    try:
        await redis_client.ping()  # Test Redis connection
        print("[MAIN] Redis connection successful.")
    except Exception as e:
        print(f"[MAIN] Redis connection failed: {e}")
        return

    # Start gateway and Celery worker concurrently
    await asyncio.gather(
        start_gateway(),
        start_celery_worker(),
    )

if __name__ == "__main__":
    asyncio.run(main())