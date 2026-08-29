from typing import List

from pymongo import MongoClient
import psycopg2

from counter.domain.models import ObjectCount
from counter.domain.ports import ObjectCountRepo


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
        counter_col = self.__get_counter_col()
        for value in new_values:
            counter_col.update_one({'object_class': value.object_class}, {'$inc': {'count': value.count}}, upsert=True)


class CountPostgresRepo(ObjectCountRepo):

    def __init__(self, host, user, password, port, database):
        self.__host = host
        self.__user = user
        self.__password = password
        self.__port = port
        self.__database = database

    def __connect(self):
        return psycopg2.connect(
            host=self.__host,
            user=self.__user,
            password=self.__password,
            port=self.__port,
            database=self.__database
        )

    def read_values(self, object_classes: List[str] = None) -> List[ObjectCount]:
        connection = self.__connect()
        try:
            with connection.cursor() as cursor:
                if object_classes:
                    cursor.execute("SELECT object_class, count FROM counter WHERE object_class IN %s",
                                   (tuple(object_classes),))
                else:
                    cursor.execute("SELECT object_class, count FROM counter")
                return [ObjectCount(object_class, count) for object_class, count in cursor.fetchall()]
        finally:
            connection.close()

    def update_values(self, new_values: List[ObjectCount]):
        connection = self.__connect()
        try:
            with connection.cursor() as cursor:
                for value in new_values:
                    cursor.execute("INSERT INTO counter (object_class, count) VALUES (%s, %s) "
                                   "ON CONFLICT (object_class) DO UPDATE "
                                   "SET count = counter.count + EXCLUDED.count",
                                   (value.object_class, value.count))
            connection.commit()
        finally:
            connection.close()
