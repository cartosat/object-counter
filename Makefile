SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: setup model env up wait down run help

# Model Variables

MODEL_NAME    := ssd_mobilenet_v2
MODEL_DIR     := tmp/model/$(MODEL_NAME)/1
MODEL_FILE    := $(MODEL_DIR)/saved_model.pb
MODEL_URL     := http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v2_coco_2018_03_29.tar.gz
MODEL_ARCHIVE := tmp/model.tar.gz
MODEL_EXTRACT := tmp/model/ssd_mobilenet_v2_coco_2018_03_29

# Docker container names (must match docker-compose.yml)
TFS_CONTAINER   := tfserving
MONGO_CONTAINER := test-mongo

# API Variables (overridable by env variables)
API_URL     ?= http://localhost:5000
SAMPLE_IMAGE ?= resources/images/cat.jpg
THRESHOLD   ?= 0.9

# Python Environment Variables
VENV       := .venv
PYTHON     := $(VENV)/bin/python
PIP        := $(VENV)/bin/pip
PYTEST     := $(VENV)/bin/pytest


setup: model env ## Setup the model and python environment


model: $(MODEL_FILE) ## Download and extract the detection model

# Download and extract the model if it doesn't exist
$(MODEL_FILE):
	@echo "Downloading $(MODEL_NAME)..."
	mkdir -p $(MODEL_DIR)
	curl -L -o $(MODEL_ARCHIVE) $(MODEL_URL)
	tar -xzf $(MODEL_ARCHIVE) -C tmp/model
	mv $(MODEL_EXTRACT)/saved_model/saved_model.pb $(MODEL_DIR)/
	rm -rf $(MODEL_ARCHIVE) $(MODEL_EXTRACT)
	chmod -R 755 tmp/model
	@echo "Model installed at $(MODEL_FILE)"

# Python environment
$(PYTHON):
	python3 -m venv $(VENV)

env: $(PYTHON)  ##  Install dependencies in a virtual environment
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt


# test: env ## Run the test suite
# 	$(PYTEST)


up: $(MODEL_FILE) ## Start the TF Serving + MongoDB
	docker compose up -d --wait


down:  ## Stop the services (MongoDB data is kept)
	docker compose down


run: up env ## Run the webapp.
	ENV=prod $(PYTHON) -m counter.entrypoints.webapp


help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'