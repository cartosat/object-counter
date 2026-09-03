# NIQ Innovation Enablement - Object Counter Challenge

The goal of this repo is demonstrate how to apply Hexagonal Architecture in a ML based system.

This application consists in a Flask API that receives an image and a threshold and returns the number of objects detected in the image.

The application is composed of three layers:

- **entrypoints**: Exposes the API and receives the requests. It is also responsible for validating the requests and returning the responses.

- **adapters**: Communicates with external services. It is responsible for translating the domain objects to the external services objects and vice-versa.

- **domain**: Business logic. It is responsible for orchestrating the calls to the external services and for applying the business rules.

The model used in this example has been taken from 
[Kaggle](https://www.kaggle.com/models/google/mobilenet-v2/tensorFlow1/openimages-v4-ssd-mobilenet-v2/1)


## Quick start

Every setup step described in this README is automated in the [`Makefile`](Makefile).
Below are few commands:

```bash
make setup   # download the model, create the virtualenv, install dependencies
make up      # start TensorFlow Serving + MongoDB, wait until both are healthy
make run     # start the API on http://localhost:5000
```

**Prerequisites:** Docker, Python >= 3.10, and GNU make.

Run `make` with no arguments to list the available tasks.

---

## Manual setup

### Instructions to setup the model (Unix)
```bash
mkdir -p tmp/model/ssd_mobilenet_v2/1
curl -L -o tmp/model.tar.gz \
  http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v2_coco_2018_03_29.tar.gz
tar -xzvf tmp/model.tar.gz -C tmp/model
mv \
    tmp/model/ssd_mobilenet_v2_coco_2018_03_29/saved_model/saved_model.pb \
    tmp/model/ssd_mobilenet_v2/1
chmod -R 777 tmp/model
rm tmp/model.tar.gz
rm -rf tmp/model/ssd_mobilenet_v2_coco_2018_03_29
```

By the end you should have the following structure:
 ```
 tmp/
  model/
    ssd_mobilenet_v2/
        1/
        saved_model.pb
 ```

### Starting the services with Docker Compose

Both services are defined in [`docker-compose.yml`](docker-compose.yml). This is what
`make up` runs, and it is the recommended manual alternative to the individual
`docker run` commands below:

```bash
docker compose up -d --wait   # --wait blocks until both containers report healthy
docker compose down           # stop (MongoDB data is kept in a named volume)
```

The individual commands below are kept for reference and for anyone not using Compose.

### Setup and run Tensorflow Serving

#### For unix systems
```bash
num_physical_cores=$(lscpu --all --parse=SOCKET,CORE | grep -v '^#' | uniq | wc -l)

docker run --rm -d \
    --name=tfserving \
    -p 8501:8501 \
    --mount type=bind,source=$(pwd)/tmp/model,target=/models \
    -e OMP_NUM_THREADS=$num_physical_cores \
    -e TENSORFLOW_INTRA_OP_PARALLELISM=$num_physical_cores \
    -e MODEL_NAME=ssd_mobilenet_v2 \
    tensorflow/serving
```

#### For Windows (Powershell)
```powershell
$num_physical_cores=(Get-WmiObject Win32_Processor | Select-Object NumberOfCores).NumberOfCores

docker run --rm -d `
    --name=tfserving `
    -p 8501:8501 `
    -v "$pwd\tmp\model:/models" `
    -e OMP_NUM_THREADS=$num_physical_cores `
    -e TENSORFLOW_INTRA_OP_PARALLELISM=$num_physical_cores `
    -e MODEL_NAME=ssd_mobilenet_v2 `
    tensorflow/serving
```

### Running MongoDB

```bash
docker run --rm --name test-mongo -p 27017:27017 -d mongo:latest
```

### Running PostgreSQL

```bash
docker run --rm --name test-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:latest
```

### Setup virtualenv (Python >= 3.10)

Unix:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=.
```

Powershell:
```powershell
python3 -m venv .venv
.venv\scripts\Activate.ps1
pip install -r requirements.txt
$Env:PYTHONPATH = "."
```


## Run the application

`DETECTOR` chooses the model backend, either `tfs` (TensorFlow Serving) or `pytorch`
(TorchServe). Whichever is in use is logged at startup:

### Using make

```bash
make run                  # PyTorch via TorchServe
make run DETECTOR=tfs     # TensorFlow Serving
```

`ENV` and `DETECTOR` are Makefile variables, so `DETECTOR=tfs make run` works too.

### Using fakes

The only path that needs neither Docker nor a downloaded model:

```bash
python -m counter.entrypoints.webapp
```

### Using real services in docker containers

Unix
```bash
ENV=prod DETECTOR=tfs python -m counter.entrypoints.webapp
ENV=prod DETECTOR=pytorch python -m counter.entrypoints.webapp
```
Powershell: 
```powershell
$env:ENV = "prod"
$env:DETECTOR = "pytorch"
python -m counter.entrypoints.webapp
```

Run `make up` first, so the model servers are up and healthy.

## Call the service

```bash
 curl -F "threshold=0.9" -F "file=@resources/images/boy.jpg" http://localhost:5000/object-count
 curl -F "threshold=0.9" -F "file=@resources/images/cat.jpg" http://localhost:5000/object-count
 curl -F "threshold=0.9" -F "file=@resources/images/food.jpg" http://localhost:5000/object-count 
```

> [!TIP]
> If you face service connectivity issues on Windows, try replacing "localhost" with "127.0.0.1" globally

## Run the tests

```
pytest
```

## Docker image for the application
### Build

Images are tagged by build date, example below:
```bash
docker build -t object-counter:2026.09.03 .
```

### Run

Start the backing services first with `make up`, then join the container to the same
network so it can reach them by service name:

```bash
docker run --rm -p 5000:5000 \
    --name counter-app \
    --network object-counter-network \
    -e ENV=prod \
    -e DETECTOR=pytorch \
    -e TFS_HOST=tfserving \
    -e TORCHSERVE_HOST=torchserve \
    -e POSTGRES_HOST=postgres \
    -e MONGO_HOST=mongo \
    object-counter:2026.09.03
```

### Stop it

```bash
docker stop counter-app
```

## Additional deep learning framework (PyTorch).

A second detector, `ssdlite320_mobilenet_v3_large`, served by TorchServe. It is also COCO trained, so it detects the same classes as the TensorFlow model.

### Instructions to setup the model (Unix)

Download the pretrained weights.

```bash
mkdir -p tmp/model/torch_ssdlite320
curl -L -o tmp/model/torch_ssdlite320/ssdlite320.pth \
  https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth
```

### Convert the weights into a model archive (One time only)

TorchServe only serves `.mar` archives, so the weights have to be packaged together with a handler. The packaging runs inside the TorchServe image, so **torch is never installed on your machine** and `requirements.txt` does not change:

```bash
mkdir -p tmp/torch-model-store

docker run --rm \
    -v "$(pwd)/torchserve:/build:ro" \
    -v "$(pwd)/tmp/model/torch_ssdlite320:/weights:ro" \
    -v "$(pwd)/tmp/torch-model-store:/model-store" \
    --entrypoint torch-model-archiver pytorch/torchserve:0.12.0-cpu \
      --model-name ssdlite320 \
      --version 1.0 \
      --handler /build/handler.py \
      --extra-files /weights/ssdlite320.pth \
      --export-path /model-store \
      --force
```

By the end you should have the following structure:
 ```
 tmp/
  model/
    torch_ssdlite320/
      ssdlite320.pth
  torch-model-store/
    ssdlite.mar
 ```

### Setup and run TorchServe

```bash
docker run --rm -d \
    --name=torchserve \
    -p 8080:8080 -p 8081:8081 -p 8082:8082 \
    --mount type=bind,source=$(pwd)/tmp/torch-model-store,target=/home/model-server/model-store \
    --mount type=bind,source=$(pwd)/torchserve/config.properties,target=/home/model-server/config.properties,readonly \
    pytorch/torchserve:0.12.0-cpu \
    torchserve --start --foreground \
        --ts-config /home/model-server/config.properties \
        --model-store /home/model-server/model-store \
        --models ssdlite=ssdlite320.mar \
        --disable-token-auth
```

### Call TorchServe directly

```bash
curl http://localhost:8080/ping
curl -X POST http://localhost:8080/predictions/ssdlite -T resources/images/cat.jpg
```

The model may takes about 30 seconds to load on first start. `ping` returns
`{"status": "Healthy"}` once it is ready.

### Stop it

```bash
docker stop torchserve
```
