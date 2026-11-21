# Known limitations (honest list)

## Not verified
* Flutter: `flutter analyze` (0 errors) and `flutter test` (20 pass) were run once on the shared package. The apps have **not been run or click-tested**; no screen was verified against the live API yet.
* `mobile_app/tool/patch_android.py` was tested only on a hand-made imitation of Flutter's generated Android files.
* **FCM push** is untested (needs Firebase credentials) and disabled by default.
* No load/performance testing; no browser or device testing of any kind.

## Not built
* Bulk CSV import of students and promotion to the next class/year.
* Password reset by email/SMS (the admin resets passwords instead).
* Urdu fonts in PDFs and UI (Latin text only; Urdu names may render as boxes in PDFs).
* Teacher timetable PDF.
* No "class teacher" role: any teacher assigned to a section can mark its attendance.
* Teachers and students have no complaints screen (admin and parents only, by design). Students have no fees screen (by design).

## Rough edges
* Fee receipt PDF shows totals but not the individual fee line items.
* Dashboard cards are not tappable; the calendar is a list per month, not a grid.
* Homework `max_marks` cannot be cleared once set.
* Attendance mark sheet has no per-student remarks field.
* The `uq_classes_name` constraint exists in the database (migration 0003) but is not declared on the SQLAlchemy model (cosmetic; autogenerate would try to drop it).
* `docs/openapi.json` is generated from the app (107 paths); regenerate after API changes.

## Security notes
* Dev seed passwords are public defaults: set `SEED_*_PASSWORD` and `APP_ENV=production` for any real use, and change `JWT_SECRET_KEY`.
* Use HTTPS in production; the cleartext option for Android is for local development only.
* The data in the seeds is fake.
