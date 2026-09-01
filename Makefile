SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: setup setup-pytorch-model model env up wait down run migrate help

# Model Variables

MODEL_NAME    := ssd_mobilenet_v2
MODEL_DIR     := tmp/model/$(MODEL_NAME)/1
MODEL_FILE    := $(MODEL_DIR)/saved_model.pb
MODEL_URL     := http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v2_coco_2018_03_29.tar.gz
MODEL_ARCHIVE := tmp/model.tar.gz
MODEL_EXTRACT := tmp/model/ssd_mobilenet_v2_coco_2018_03_29

# PyTorch / TorchServe model (one time setup, see setup-pytorch-model)
TORCH_MODEL_DIR   := tmp/model/torch_ssdlite320
TORCH_WEIGHTS     := $(TORCH_MODEL_DIR)/ssdlite320.pth
TORCH_WEIGHTS_URL := https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth
TORCH_MODEL_STORE := tmp/torch-model-store
TORCH_MAR_FILE    := $(TORCH_MODEL_STORE)/ssdlite.mar
TORCHSERVE_IMAGE  := pytorch/torchserve:0.12.0-cpu

# Docker container names (must match docker-compose.yml)
TFS_CONTAINER   := tfserving
MONGO_CONTAINER := test-mongo

# Postgres (must match docker-compose.yml)
POSTGRES_USER ?= postgres
POSTGRES_DB   ?= prod_counter

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

setup-pytorch-model: $(TORCH_MAR_FILE) ## One time setup: download PyTorch weights and build ssdlite.mar

# Download the pretrained weights. A single file, nothing to extract.
$(TORCH_WEIGHTS):
	@echo "Downloading ssdlite320_mobilenet_v3_large weights..."
	mkdir -p $(TORCH_MODEL_DIR)
	curl -L -o $(TORCH_WEIGHTS) $(TORCH_WEIGHTS_URL)

# Package the weights with the handler into a .mar. Runs inside the TorchServe image,
# so torch is never installed on the host. The container removes itself when done.
$(TORCH_MAR_FILE): $(TORCH_WEIGHTS) torchserve/handler.py
	@echo "Building $(TORCH_MAR_FILE)..."
	mkdir -p $(TORCH_MODEL_STORE)
	docker run --rm \
	    -v "$(PWD)/torchserve:/build:ro" \
	    -v "$(PWD)/$(TORCH_MODEL_DIR):/weights:ro" \
	    -v "$(PWD)/$(TORCH_MODEL_STORE):/model-store" \
	    --entrypoint torch-model-archiver $(TORCHSERVE_IMAGE) \
	      --model-name ssdlite \
	      --version 1.0 \
	      --handler /build/handler.py \
	      --extra-files /weights/ssdlite320.pth \
	      --export-path /model-store \
	      --force
	@echo "Built $(TORCH_MAR_FILE)"

# Python environment
$(PYTHON):
	python3 -m venv $(VENV)

env: $(PYTHON)  ##  Install dependencies in a virtual environment
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt


# test: env ## Run the test suite
# 	$(PYTEST)


up: $(MODEL_FILE) $(TORCH_MAR_FILE) ## Start TF Serving + TorchServe + MongoDB + Postgres
	docker compose up -d --wait


migrate:  ## Apply sql/schema.sql to a running Postgres (initdb only runs on a fresh volume)
	docker compose exec -T postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB) -f - < sql/schema.sql

down:  ## Stop the services (MongoDB data is kept)
	docker compose down


run: up env ## Run the webapp.
	ENV=prod $(PYTHON) -m counter.entrypoints.webapp


help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'