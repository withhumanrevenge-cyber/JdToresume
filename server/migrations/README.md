# server/migrations: Alembic

Run from the repo root (`alembic.ini` is there; the database URL comes from `DATABASE_URL`):
- apply: `.venv/Scripts/python.exe -m alembic upgrade head`
- new migration after changing a model: `.venv/Scripts/python.exe -m alembic revision --autogenerate -m "what changed"`,
  then **read and tidy the generated file** before committing; `alembic check` must report no drift.

Migrations so far: users / contact details / career profiles, then jobs, then applications / generation runs /
artifacts / the llm_calls cost ledger.

Rules: every model module is imported in `server/app/models.py`; migrations stay backward compatible
(expand -> migrate -> contract) and run as a one-off ECS task before the new task set takes traffic.
