import logging
import os


def setup_logging(service_name: str = "juldyz"):
    fmt = logging.Formatter(
        f"[%(asctime)s] [{service_name}/%(levelname)s]: %(message)s",
        datefmt="%H:%M:%S"
    )

    handler = logging.StreamHandler()
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    os.environ["JULDYZ_LOGGING"] = "1"