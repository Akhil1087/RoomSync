# RoomSync — Roommate / Flatmate Compatibility Matcher

A Flask full-stack prototype for student roommate discovery around real PG/Flat listings.

## Run locally

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Demo accounts

Admin: `/admin/login`
- username: `admin`
- password: `admin123`

Student accounts can be created through `/register`.

The app seeds 3 sample PGs on the first run. Student profiles and contact requests are stored in SQLite.

## Deployment

For Render/Railway/etc. use:

Build: `pip install -r requirements.txt`
Start: `gunicorn app:app`

Set a strong `SECRET_KEY` in production. For persistent multi-user deployment, set `DATABASE_URL` to PostgreSQL/MySQL instead of SQLite. Configure `CAMPUS_LAT` and `CAMPUS_LON` for the actual campus.

## Notes

- Student and admin sessions are separated by role and checked server-side.
- Matching uses Budget 20%, Cleanliness 20%, Sleep 20%, Food 15%, Social 15%, Study 10%.
- Maps use Leaflet + OpenStreetMap tiles.
- The assistant is intentionally rule-based and does not require an external AI API.
