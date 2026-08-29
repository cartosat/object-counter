import os

from counter.adapters.count_repo import CountMongoDBRepo, CountInMemoryRepo, CountPostgresRepo
from counter.adapters.object_detector import TFSObjectDetector, FakeObjectDetector
from counter.domain.actions import CountDetectedObjects, DetectObjects


def dev_count_action() -> CountDetectedObjects:
    return CountDetectedObjects(FakeObjectDetector(), CountInMemoryRepo())


def prod_count_action() -> CountDetectedObjects:
    tfs_host = os.environ.get('TFS_HOST', 'localhost')
    tfs_port = os.environ.get('TFS_PORT', 8501)
    model_name = os.environ.get('MODEL_NAME', 'ssd_mobilenet_v2')
    mongo_host = os.environ.get('MONGO_HOST', 'localhost')
    mongo_port = os.environ.get('MONGO_PORT', 27017)
    mongo_db = os.environ.get('MONGO_DB', 'prod_counter')
    postgres_host = os.environ.get('POSTGRES_HOST', 'localhost')
    postgres_user = os.environ.get('POSTGRES_USER', 'postgres')
    postgres_password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
    postgres_port = os.environ.get('POSTGRES_PORT', 5432)
    postgres_db = os.environ.get('POSTGRES_DB', 'prod_counter')

    return CountDetectedObjects(TFSObjectDetector(tfs_host, tfs_port, model_name),
                                CountPostgresRepo(host=postgres_host, user=postgres_user, password=postgres_password, port=postgres_port, database=postgres_db))

def dev_detect_action():
    return DetectObjects(FakeObjectDetector())

def prod_detect_action():
    tfs_host = os.environ.get('TFS_HOST', 'localhost')
    tfs_port = os.environ.get('TFS_PORT', 8501)
    model_name = os.environ.get('MODEL_NAME', 'ssd_mobilenet_v2')
    return DetectObjects(TFSObjectDetector(tfs_host, tfs_port, model_name))

def get_count_action() -> CountDetectedObjects:
    env = os.environ.get('ENV', 'dev')
    count_action_fn = f"{env}_count_action"
    return globals()[count_action_fn]()

def get_detect_action() -> DetectObjects:
    env = os.environ.get('ENV', 'dev')
    detect_action_fn = f"{env}_detect_action"
    return globals()[detect_action_fn]()