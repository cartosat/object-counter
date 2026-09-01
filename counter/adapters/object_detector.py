import json
from typing import List, BinaryIO

import numpy as np
import requests
from PIL import Image

from counter.domain.models import Prediction, Box
from counter.domain.ports import ObjectDetector


class FakeObjectDetector(ObjectDetector):
    def predict(self, image: BinaryIO) -> List[Prediction]:
        return [Prediction(class_name='cat',
                           score=0.999190748,
                           box=Box(xmin=0.367288858, ymin=0.278333426,
                                   xmax=0.735821366, ymax=0.6988855)
                           ),
                ]


class TFSObjectDetector(ObjectDetector):
    def __init__(self, host, port, model):
        self.url = f"http://{host}:{port}/v1/models/{model}:predict"
        self.classes_dict = self.__build_classes_dict()

    def predict(self, image: BinaryIO) -> List[Prediction]:
        np_image = self.__to_np_array(image)
        predict_request = '{"instances" : %s}' % np.expand_dims(np_image, 0).tolist()        
        print(f"Sending request to TFS...{self.url}")
        response = requests.post(self.url, data=predict_request)
        predictions = response.json()['predictions'][0]
        return self.__raw_predictions_to_domain(predictions)

    @staticmethod
    def __build_classes_dict():
        with open('counter/adapters/mscoco_label_map.json') as json_file:
            labels = json.load(json_file)
            return {label['id']: label['display_name'] for label in labels}

    @staticmethod
    def __to_np_array(image: BinaryIO):
        image_ = Image.open(image)
        (im_width, im_height) = image_.size
        return np.array(image_.getdata()).reshape((im_height, im_width, 3)).astype(np.uint8)

    def __raw_predictions_to_domain(self, raw_predictions: dict) -> List[Prediction]:
        print("Parsing raw predictions...")
        num_detections = int(raw_predictions.get('num_detections'))
        predictions = []
        for i in range(0, num_detections):
            detection_box = raw_predictions['detection_boxes'][i]
            box = Box(xmin=detection_box[1], ymin=detection_box[0], xmax=detection_box[3], ymax=detection_box[2])
            detection_score = raw_predictions['detection_scores'][i]
            detection_class = raw_predictions['detection_classes'][i]
            class_name = self.classes_dict[detection_class]
            predictions.append(Prediction(class_name=class_name, score=detection_score, box=box))
        print(predictions)
        return predictions


class PyTorchObjectDetector(ObjectDetector):
    """Detects objects using a PyTorch model served by TorchServe."""

    def __init__(self, host: str, port: int, model: str):
        self.url = f"http://{host}:{port}/predictions/{model}"

    def predict(self, image: BinaryIO) -> List[Prediction]:
        image.seek(0)
        response = requests.post(self.url, data=image.read())
        response.raise_for_status()
        return self.__raw_predictions_to_domain(response.json())

    def __raw_predictions_to_domain(self, raw_predictions: dict) -> List[Prediction]:
        image_size = raw_predictions['image_size']
        return [
            Prediction(
                class_name=detection['class_name'],
                score=detection['score'],
                box=self.__to_normalized_box(detection['box'], image_size),
            )
            for detection in raw_predictions['detections']
        ]

    @staticmethod
    def __to_normalized_box(box: List[float], image_size: dict) -> Box:
        """TorchServe returns pixel coordinates, the domain expects 0 to 1 ratios."""
        xmin, ymin, xmax, ymax = box
        width, height = image_size['width'], image_size['height']
        return Box(xmin=xmin / width, ymin=ymin / height,
                   xmax=xmax / width, ymax=ymax / height)
