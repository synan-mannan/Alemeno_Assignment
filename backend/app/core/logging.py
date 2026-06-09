import json
import logging
import os
import sys
from loguru import logger
from app.core.config import settings


def serialize(record):
    """Serialize log record to JSON format for production environments."""
    subset = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "request_id": record["extra"].get("request_id", ""),
        "task_id": record["extra"].get("task_id", ""),
    }
    if record["exception"]:
        subset["exception"] = record["exception"]
    return json.dumps(subset)


def json_sink(message):
    serialized = serialize(message.record)
    sys.stdout.write(serialized + "\n")
    sys.stdout.flush()


def setup_logging(is_production: bool = False):
    # Intercept standard logging messages
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            frame = logging.currentframe()
            depth = 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Disable default loggers from other libraries to prevent spam
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn").handlers = []
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)

    # Configure Loguru
    logger.remove()

    if is_production:
        # Production JSON logging to stdout
        logger.add(
            json_sink,
            level="INFO",
            colorize=False,
            backtrace=True,
            diagnose=False,
        )
    else:
        # Human-readable colored console logging
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level> "
            "<light-black>{extra}</light-black>"
        )
        logger.add(
            sys.stdout,
            format=log_format,
            level="DEBUG",
            colorize=True,
            backtrace=True,
            diagnose=True,
        )


# Initialize logging configuration based on execution environment
is_prod = os.getenv("ENV", "development").lower() == "production"
setup_logging(is_production=is_prod)
