# Campsite Booking Local

Minimal local prototype for campsite and house booking.

## What it does

- public availability search by `check_in`, `check_out`, and `guest_count`
- `Laski rovt ZTS` split into `Subcamp 1`, `Subcamp 2`, and `Subcamp 3`
- `Laski rovt ZR`, `Laski rovt MB`, `Taborni prostor Ukanc`, `Gozdna sola Ukanc`, `Taborni prostor Baredi`, and `Taborni prostor Radlje ob Dravi`
- per-night capacity checks
- `pending` and `confirmed` bookings reserve capacity
- price calculated per guest per night
- admin page for status updates and manual overbooked bookings

## Run locally

```powershell
cd C:\Users\Uporabnik\campsite-booking-local
python app.py
```

Open `http://127.0.0.1:8000`.

## Notes

- Data is stored in `booking.db` next to the app.
- The database is created automatically and startup syncs the seeded campsite list.
- Run `reset_db.bat` if you want to wipe all local bookings and rebuild the database from scratch.
- This is intentionally a small prototype so the booking rules can be refined before moving to a larger stack.

## Deploy to Render

This folder now includes the minimum Render files:

- `render.yaml`
- `requirements.txt`
- `.python-version`
- `wsgi.py`

Use this flow:

1. Put this folder in its own GitHub repository.
2. In Render, create a new `Blueprint` or `Web Service` from that repository.
3. Render will use:
   - build command: `pip install -r requirements.txt`
   - start command: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 wsgi:application`

Important limitation:

- Render free web services are fine for testing, but this app still uses local SQLite in `booking.db`.
- That means bookings are not a durable production database on Render yet.
- For a real public launch, the next step is moving bookings to PostgreSQL.
