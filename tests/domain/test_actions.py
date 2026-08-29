from unittest.mock import Mock

import pytest

from counter.domain.actions import CountDetectedObjects, DetectObjects
from counter.domain.models import Box, ObjectCount, Prediction
from tests.domain.helpers import generate_prediction


class TestCountDetectedObjects:
    @pytest.fixture
    def object_detector(self) -> Mock:
        object_detector = Mock()
        object_detector.predict.return_value = [generate_prediction('cat', 0.9),
                                                generate_prediction('cat', 0.8),
                                                generate_prediction('dog', 0.8),
                                                generate_prediction('dog', 0.1),
                                                generate_prediction('rabbit', 0.9)]
        return object_detector

    @pytest.fixture
    def count_object_repo(self) -> Mock:
        return Mock()

    def test_count_valid_predictions(self, object_detector, count_object_repo) -> None:
        response = CountDetectedObjects(object_detector, count_object_repo).execute(None, 0.5)
        assert sorted(response.current_objects, key=lambda x: x.object_class) == \
            [ObjectCount('cat', 2), ObjectCount('dog', 1), ObjectCount('rabbit', 1)]

    def test_update_count_object_repo(self, object_detector, count_object_repo):
        CountDetectedObjects(object_detector, count_object_repo).execute(None, 0)
        count_object_repo.update_values.assert_called_with(
            [ObjectCount('cat', 2), ObjectCount('dog', 2), ObjectCount('rabbit', 1)])


class TestDetectObjects:
    @pytest.fixture
    def object_detector(self) -> Mock:
        object_detector = Mock()
        object_detector.predict.return_value = [generate_prediction('cat', 0.9),
                                                generate_prediction('cat', 0.8),
                                                generate_prediction('dog', 0.8),
                                                generate_prediction('dog', 0.1),
                                                generate_prediction('rabbit', 0.9)]
        return object_detector

    def test_returns_only_predictions_over_threshold(self, object_detector) -> None:
        predictions = DetectObjects(object_detector).execute(None, 0.85)
        assert predictions == [generate_prediction('cat', 0.9),
                               generate_prediction('rabbit', 0.9)]

    def test_threshold_is_inclusive(self, object_detector) -> None:
        predictions = DetectObjects(object_detector).execute(None, 0.9)
        assert [prediction.score for prediction in predictions] == [0.9, 0.9]

    def test_returns_every_prediction_when_threshold_is_zero(self, object_detector) -> None:
        predictions = DetectObjects(object_detector).execute(None, 0)
        assert len(predictions) == 5

    def test_returns_empty_list_when_nothing_passes_threshold(self, object_detector) -> None:
        predictions = DetectObjects(object_detector).execute(None, 1.0)
        assert predictions == []

    def test_returns_domain_predictions_with_class_score_and_box(self, object_detector) -> None:
        predictions = DetectObjects(object_detector).execute(None, 0.85)
        assert all(isinstance(prediction, Prediction) for prediction in predictions)
        assert predictions[0].class_name == 'cat'
        assert predictions[0].score == 0.9
        assert predictions[0].box == Box(0, 0, 0, 0)

    def test_passes_the_image_to_the_detector(self, object_detector) -> None:
        image = object()
        DetectObjects(object_detector).execute(image, 0.5)
        object_detector.predict.assert_called_once_with(image)
