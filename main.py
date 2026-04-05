from core.gateway import app as gateway_app
from core.config import GATEWAY_HOST, GATEWAY_PORT, LOG_LEVEL
import uvicorn

def start_gateway():
    """
    Start the FastAPI gateway.
    """
    print("[MAIN] Starting gateway...")
    config = {"host": "0.0.0.0", "port": 8000, "log_level": "info"}
    uvicorn.run(gateway_app, **config)

def main():
    uvicorn.run(gateway_app, host=GATEWAY_HOST, port=GATEWAY_PORT, log_level=LOG_LEVEL)
    print(f"[MAIN] starting api on :{GATEWAY_PORT}")
 
if __name__ == "__main__":
    main()