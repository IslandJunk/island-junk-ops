# Island Junk Ops — developer setup

Backend: **FastAPI + SQLAlchemy 2 + Postgres** (Python 3.14), serving the approved
`/prototypes` screens with a data layer swapped in for their `localStorage`.
Deploy target: **Render**. Brand-aware from day one (`victoria` | `nanaimo`).

## Layout
```
app/
  core/config.py      # settings (.env)
  db/base.py          # Base + UUID/Timestamp/BrandScoped mixins
  db/session.py       # lazy engine + get_db() dependency
  models/enums.py     # settled enums (Brand, DeviceType, PayType)
  main.py             # FastAPI app (/health)
docs/data-model.md    # full target schema + OPEN DECISIONS
migrations/           # alembic (added once a DB is connected)
prototypes/           # approved screens (the UI spec — ported, not rebuilt)
spike/                # calendar stack-order proof (done)
```

## First run
```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate; pip install -r requirements.txt  # *nix

cp .env.example .env            # then set DATABASE_URL + SESSION_SECRET
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
# -> http://127.0.0.1:8000/health
```

## Database
Set `DATABASE_URL` in `.env` (SQLAlchemy + psycopg3 form):
`postgresql+psycopg://user:pass@host:5432/db`. Easiest is a **Render Postgres** instance
(matches deploy). The app boots without a DB (for `/health`); migrations need one.

## Guardrails (see CLAUDE.md §2, §15)
Never write to a live Google Calendar (TEST calendar only until go-live). Never auto-invoice/charge.
Never store full card numbers/CVVs. Never let a job save without a crew name. Never hardcode staff/truck names.
