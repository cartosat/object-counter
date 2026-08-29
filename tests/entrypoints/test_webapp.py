import io
import json

import pytest

from pathlib import Path
from counter.entrypoints.webapp import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def image_path():
    ref_dir = Path(__file__).parent
    return ref_dir.parent.parent / "resources" / "images" / "boy.jpg"

#  Helper function to post an image to the Flask app.
def post_image(client, url, image_path, threshold=None):
    with open(image_path, 'rb') as f:
        image = io.BytesIO(f.read())

    data = {'file': (image, 'test.jpg')}
    if threshold is not None:
        data['threshold'] = str(threshold)

    return client.post(url, data=data,
                       content_type='multipart/form-data', buffered=True)


def test_object_detection(client, image_path):
    # Load the image from the path resource/boy.jpg
    with open(image_path, 'rb') as f:
        image_data = f.read()
    image = io.BytesIO(image_data)

    data = {
        'threshold': '0.9',
        'model_name': 'ssd_mobilenet_v2',
    }
    data['file'] = (image, 'test.jpg')

    # Make a test request to the object_detection endpoint
    response = client.post('/object-count', data = data,
        content_type='multipart/form-data', buffered=True)

    # Check that the count_action was called with the correct arguments and
    # and status code is correct(Integration test)
    assert response.status_code == 200
    assert json.loads(response.data) != None



def test_object_list_returns_predictions_over_threshold(client, image_path):
    response = post_image(client, '/object-list', image_path, threshold=0.9)

    predictions = json.loads(response.data)
    assert response.status_code == 200
    assert len(predictions) == 1
    assert predictions[0]['class_name'] == 'cat'
    assert predictions[0]['score'] == pytest.approx(0.999190748)
    assert sorted(predictions[0]['box']) == ['xmax', 'xmin', 'ymax', 'ymin']


def test_object_list_filters_out_predictions_below_threshold(client, image_path):
    response = post_image(client, '/object-list', image_path, threshold=1.0)

    assert response.status_code == 200
    assert json.loads(response.data) == []


def test_object_list_uses_a_default_threshold(client, image_path):
    response = post_image(client, '/object-list', image_path)

    assert len(json.loads(response.data)) == 1
