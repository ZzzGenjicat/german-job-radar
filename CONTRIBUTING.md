# Contributing

This page is for code contributors. Using the [Windows download](https://github.com/ZzzGenjicat/german-job-radar/releases/latest) does not require installing Python or any development tools.

## Development checks

The source project uses Windows/Python 3.11+ with a virtual environment and Node.js for JavaScript syntax checks. In a prepared development environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check web/app.js
```

Offline tests use synthetic fixtures. CI runs Windows/Python 3.11–3.13.

## Releases

The public source builder copies an explicit allowlist, rejects symlinks and checks obvious secrets/machine paths. Review the output because automated checks cannot detect every secret. Choose a new, empty destination outside the source tree:

```powershell
.\.venv\Scripts\python.exe tools/build_release.py --destination ..\job-radar-public --zip ..\job-radar-public.zip
```

Build the Windows executable in a clean Windows/Python x64 environment with `requirements-build.txt`, then run `python tools/build_exe.py` and `python tools/smoke_exe.py dist/GermanJobRadar-Windows-x64.exe` (the smoke requires `requirements-dev.txt`). Publishing a GitHub Release triggers the Windows build, offline tests, frozen runtime smoke and asset upload. The spec bundles web assets, DOCX templates and tzdata; no `data/`, CVs, local settings or keys are bundled.

If a release upload times out, run **Actions → Windows download → Run workflow** on `main` and enter the existing version tag. It rebuilds that tag, repeats all checks, then replaces that release's download files. Uploads run one file at a time with up to three attempts; the checksum manifest is uploaded last. Runs for the same tag are serialized. This does not move the tag or change the application source.

## Contribution guidelines

Keep parsing separate from fetching. New adapters require synthetic search/detail/failure fixtures, original vs modified date checks and explicit parse errors. Do not commit real CVs, downloaded pages with personal contact data, credentials or histories. Do not bypass CAPTCHAs or restricted endpoints.

Terminology lives in radar/terms.py. Expansion requires two distinct eligible JDs and must preserve deletions. JD terms are not applicant skills. Migrations must preserve settings/data. Visible grouping is in radar/presentation.py; UI and CSV numbers must agree.

For issues, provide reproduction steps and redacted errors. Remove keys, CV text, names, local paths and application data before sharing logs.
