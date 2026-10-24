-- Runs once, when the local Postgres volume is first created (docker-compose.yml).
-- The dev database "tailor" is created by the image itself; tests use their own database so they can wipe it freely.
CREATE DATABASE tailor_test OWNER tailor;
