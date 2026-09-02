"""TorchServe handler for SSDLite320 MobileNetV3.

Builds the torchvision model and loads the downloaded .pth itself, so no separate
conversion step is needed.

Returns every detection with pixel boxes plus the image size. Score filtering is
deliberately left to the application, which takes the threshold from the caller.
"""
import base64
import io
import json
import os

import torch
from PIL import Image
from torchvision import transforms
from torchvision.models.detection import (
    ssdlite320_mobilenet_v3_large,
    SSDLite320_MobileNet_V3_Large_Weights,
)
from ts.torch_handler.base_handler import BaseHandler


class SSDLiteHandler(BaseHandler):

    def initialize(self, context):
        model_dir = context.system_properties.get("model_dir")
        self.device = torch.device("cpu")

        # weights=None so torchvision downloads nothing. The .pth packaged into the
        # archive is loaded instead, which keeps startup offline.
        weights_path = os.path.join(model_dir, "ssdlite320.pth")
        self.model = ssdlite320_mobilenet_v3_large(weights=None, weights_backbone=None)
        self.model.load_state_dict(
            torch.load(weights_path, map_location="cpu", weights_only=True))
        self.model.eval()

        # Class names are metadata inside torchvision, no download needed.
        self.categories = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1.meta["categories"]
        self.to_tensor = transforms.ToTensor()
        self.initialized = True

    def preprocess(self, data):
        self.sizes = []
        images = []
        for row in data:
            raw = row.get("data") or row.get("body")
            if isinstance(raw, str):
                raw = base64.b64decode(raw)
            image = Image.open(io.BytesIO(raw)).convert("RGB")
            self.sizes.append(image.size)
            images.append(self.to_tensor(image).to(self.device))
        return images

    def inference(self, data, *args, **kwargs):
        with torch.no_grad():
            return self.model(data)

    def postprocess(self, data):
        results = []
        for prediction, (width, height) in zip(data, self.sizes):
            detections = [
                {
                    "class_name": self.categories[int(label)],
                    "score": float(score),
                    "box": [float(value) for value in box],
                }
                for box, label, score in zip(
                    prediction["boxes"], prediction["labels"], prediction["scores"]
                )
            ]
            results.append({
                "image_size": {"width": width, "height": height},
                "detections": detections,
            })
        return results
