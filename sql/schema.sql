-- Schema for the object counter.
--
-- Below schema will be automatically applied during container initilization as
-- this file is mentioned tentrypoint in the docker-compose.yml file.

CREATE TABLE IF NOT EXISTS counter (
    object_class VARCHAR(255) PRIMARY KEY,
    count        INTEGER NOT NULL DEFAULT 0
);
