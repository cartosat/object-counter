import os

from counter.adapters.count_repo import CountMongoDBRepo, CountInMemoryRepo, CountPostgresRepo
from counter.adapters.object_detector import TFSObjectDetector, FakeObjectDetector, PyTorchObjectDetector
from counter.domain.ports import ObjectDetector
from counter.domain.actions import CountDetectedObjects, DetectObjects


def get_detector_name() -> str:
    """Model backend in use. Reported at startup, dev always uses the fake one."""
    if os.environ.get('ENV', 'dev') == 'dev':
        return 'fake'
    return os.environ.get('DETECTOR', 'tfs')


def build_detector() -> ObjectDetector:
    detector_name = get_detector_name()
    if detector_name == 'tfs':
        return TFSObjectDetector(os.environ.get('TFS_HOST', 'localhost'),
                                 os.environ.get('TFS_PORT', 8501),
                                 os.environ.get('MODEL_NAME', 'ssd_mobilenet_v2'))
    if detector_name == 'pytorch':
        return PyTorchObjectDetector(os.environ.get('TORCHSERVE_HOST', 'localhost'),
                                     os.environ.get('TORCHSERVE_PORT', 8080),
                                     os.environ.get('TORCHSERVE_MODEL', 'ssdlite'))
    raise ValueError(f"Unknown DETECTOR '{detector_name}'. Valid values are: tfs, pytorch")


def dev_count_action() -> CountDetectedObjects:
    return CountDetectedObjects(FakeObjectDetector(), CountInMemoryRepo())


def prod_count_action() -> CountDetectedObjects:
    mongo_host = os.environ.get('MONGO_HOST', 'localhost')
    mongo_port = os.environ.get('MONGO_PORT', 27017)
    mongo_db = os.environ.get('MONGO_DB', 'prod_counter')
    postgres_host = os.environ.get('POSTGRES_HOST', 'localhost')
    postgres_user = os.environ.get('POSTGRES_USER', 'postgres')
    postgres_password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
    postgres_port = os.environ.get('POSTGRES_PORT', 5432)
    postgres_db = os.environ.get('POSTGRES_DB', 'prod_counter')

    return CountDetectedObjects(build_detector(),
                                CountPostgresRepo(host=postgres_host, user=postgres_user, password=postgres_password, port=postgres_port, database=postgres_db))

def dev_detect_action():
    return DetectObjects(FakeObjectDetector())

def prod_detect_action():
    return DetectObjects(build_detector())

def get_count_action() -> CountDetectedObjects:
    env = os.environ.get('ENV', 'dev')
    count_action_fn = f"{env}_count_action"
    return globals()[count_action_fn]()

def get_detect_action() -> DetectObjects:
    env = os.environ.get('ENV', 'dev')
    detect_action_fn = f"{env}_detect_action"
    return globals()[detect_action_fn]()