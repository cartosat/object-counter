import logging
from io import BytesIO

from flask import Flask, request, jsonify

from counter import config
from counter.logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app():
    configure_logging()

    app = Flask(__name__)

    logger.info("Using %s as object detector", config.get_detector_name())

    count_action = config.get_count_action()
    detect_action = config.get_detect_action()

    def _read_request():
        threshold = float(request.form.get('threshold', 0.5))
        image = BytesIO()
        request.files['file'].save(image)
        return image, threshold
    
    @app.route('/object-count', methods=['POST'])
    def count_objects():
        image, threshold = _read_request()
        return jsonify(count_action.execute(image, threshold))


    @app.route('/object-list', methods=['POST'])
    def list_predictions():
        image, threshold = _read_request()
        return jsonify(detect_action.execute(image, threshold))

    return app

if __name__ == '__main__':
    app = create_app()
    app.run('0.0.0.0', debug=True)
