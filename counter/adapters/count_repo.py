from contextlib import contextmanager
import logging
from typing import List

from pymongo import MongoClient
from psycopg2.pool import SimpleConnectionPool

from counter.domain.models import ObjectCount
from counter.domain.ports import ObjectCountRepo

logger = logging.getLogger(__name__)


class CountInMemoryRepo(ObjectCountRepo):

    def __init__(self):
        self.store = dict()

    def read_values(self, object_classes: List[str] = None) -> List[ObjectCount]:
        if object_classes is None:
            return list(self.store.values())

        return [self.store.get(object_class) for object_class in object_classes]

    def update_values(self, new_values: List[ObjectCount]):
        for new_object_count in new_values:
            key = new_object_count.object_class
            try:
                stored_object_count = self.store[key]
                self.store[key] = ObjectCount(key, stored_object_count.count + new_object_count.count)
            except KeyError:
                self.store[key] = ObjectCount(key, new_object_count.count)


class CountMongoDBRepo(ObjectCountRepo):

    def __init__(self, host, port, database):
        self.__host = host
        self.__port = port
        self.__database = database

    def __get_counter_col(self):
        client = MongoClient(self.__host, self.__port)
        db = client[self.__database]
        counter_col = db.counter
        return counter_col

    def read_values(self, object_classes: List[str] = None) -> List[ObjectCount]:
        counter_col = self.__get_counter_col()
        query = {"object_class": {"$in": object_classes}} if object_classes else None
        counters = counter_col.find(query)
        object_counts = []
        for counter in counters:
            object_counts.append(ObjectCount(counter['object_class'], counter['count']))
        return object_counts

    def update_values(self, new_values: List[ObjectCount]):
        logger.debug("Updating %d object counts in MongoDB", len(new_values))
        counter_col = self.__get_counter_col()
        for value in new_values:
            counter_col.update_one({'object_class': value.object_class}, {'$inc': {'count': value.count}}, upsert=True)


class CountPostgresRepo(ObjectCountRepo):

    def __init__(self, host, user, password, port, database, min_connections=1, max_connections=5):
        self.__pool = SimpleConnectionPool(min_connections, max_connections,
                                           host=host, user=user, password=password,
                                           port=port, database=database)

    @contextmanager
    def __connection(self):
        """Lend a pooled connection, committing on success and always returning it."""
        connection = self.__pool.getconn()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            self.__pool.putconn(connection)

    def read_values(self, object_classes: List[str] = None) -> List[ObjectCount]:
        with self.__connection() as connection, connection.cursor() as cursor:
            if object_classes:
                cursor.execute("SELECT object_class, count FROM counter WHERE object_class IN %s",
                               (tuple(object_classes),))
            else:
                cursor.execute("SELECT object_class, count FROM counter")
            return [ObjectCount(object_class, count) for object_class, count in cursor.fetchall()]

    def update_values(self, new_values: List[ObjectCount]):
        logger.debug("Updating %d object counts in Postgres", len(new_values))
        with self.__connection() as connection, connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO counter (object_class, count) VALUES (%s, %s) "
                "ON CONFLICT (object_class) DO UPDATE "
                "SET count = counter.count + EXCLUDED.count",
                [(value.object_class, value.count) for value in new_values])

    def close(self):
        self.__pool.closeall()
