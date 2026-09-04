import logging
import os

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging() -> None:
    """Configure logging once, from an entrypoint.

    Level comes from LOG_LEVEL and defaults to INFO. Set LOG_LEVEL=DEBUG to see the
    per request detail from the adapters.

    Every other module only calls logging.getLogger(__name__).
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format=LOG_FORMAT, force=True)
