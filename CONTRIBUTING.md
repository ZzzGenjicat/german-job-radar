# Contributing

Use Windows/Python 3.11+, install requirements-dev.txt, run the offline unittest suite and `node --check web/app.js`.

Keep parsing separate from fetching. New adapters require synthetic search/detail/failure fixtures, original vs modified date checks and explicit parse errors. Do not commit real CVs, downloaded pages with personal contact data, credentials or histories. Do not bypass CAPTCHAs or restricted endpoints.

Terminology lives in radar/terms.py. Expansion requires two distinct eligible JDs and must preserve deletions. JD terms are not applicant skills. Migrations must preserve settings/data. Visible grouping is in radar/presentation.py; UI and CSV numbers must agree.

For issues, provide reproduction steps and redacted errors. Remove keys, CV text, names, local paths and application data before sharing logs.
