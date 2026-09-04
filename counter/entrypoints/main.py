import logging
import sys

from counter import config
from counter.logging_config import configure_logging

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    configure_logging()
    img_path = sys.argv[1]
    threshold = float(sys.argv[2])
    logger.info("Counting objects in %s above threshold %s using %s",
                img_path, threshold, config.get_detector_name())
    with open(img_path, 'rb') as img:
        predictions = config.get_count_action().execute(img, threshold)

        print(predictions)
