# German Job Radar

A local Windows dashboard for German job searches. Use your own keywords, inspect captured job descriptions and evidence, and export an Excel-friendly CSV. The interface is currently Chinese; German and English job content is preserved.

[中文说明](docs/USAGE.zh-CN.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT license](LICENSE)

## Download for Windows — no Python required

Download [GermanJobRadar-Windows-x64.zip](https://github.com/ZzzGenjicat/german-job-radar/releases/latest/download/GermanJobRadar-Windows-x64.zip), extract it and double-click the EXE. Or download the [standalone EXE](https://github.com/ZzzGenjicat/german-job-radar/releases/latest/download/GermanJobRadar-Windows-x64.exe). Windows 10/11 x64; no administrator or Python installation needed. See [Windows instructions](docs/WINDOWS.md), license notices and SHA256 checksums in [Releases](https://github.com/ZzzGenjicat/german-job-radar/releases).

The bundled app saves data in `%LOCALAPPDATA%\GermanJobRadar`, independent of the EXE's location. Exit in the dashboard before replacing the EXE; history stays. Optional 18:00 scheduling can be enabled/disabled in search settings. Keep the EXE at a fixed location, or re-enable scheduling after moving it. The executable is currently unsigned.

## Features

- Regular employment, internships and/or working-student roles. Full-time is a separate option; turn it off to accept part-time. Junior is allowed unless you add it to exclusions.
- Editable keywords, optional themes and exclusion words. Initial AI/CRM terms are examples, not fixed restrictions. For regular jobs, use broad terms such as `Buchhaltung` or `CRM` without an `Intern` prefix.
- Optional **local first-scan expansion** from an inspectable terminology map. A related term must appear in at least two distinct eligible JDs. At most ten additions, with evidence, used on the **next** scan. Deleted or renamed terms are blocked from automatic re-addition. No API key/cloud request.
- Two lists: **待人工筛查** (manual screening) and **已排除** (excluded). Cards distinguish passed checks from evidence gaps. Human judgement is still required.
- Manual rolling 24-hour scans; optional weekday 18:00 Europe/Berlin scans. Later scans default to unseen jobs. First discovery is not publication time.
- Stable batch-wide numbers. CSV exports **both complete lists**, including records hidden by “new only”, with the title `德国岗位雷达（只作为建议）` and a separate column-header row. Numbers match the dashboard.
- Links open in the OS default browser. No automatic applications, bookmarks, Google Drive or spreadsheet sync.
- Optional local PDF/DOCX extraction and OpenAI keyword drafting/feedback analysis. AI drafts require your confirmation, your own API key and may incur charges. A ChatGPT subscription is not an API key.

## Install from source (developers)

Requirements: Windows 10/11, Python 3.11+ with venv/pip, network access for installation and searches. Tested with Python 3.12. Install from [python.org](https://www.python.org/downloads/windows/).

From the extracted project folder in PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\launch.ps1
# Optional explicit interpreter:
.\setup.ps1 -Python "C:\path\to\python.exe"
```

After setup you can double-click `打开德国岗位雷达.cmd`. The app opens at `http://127.0.0.1:48218`. **First launch does not search.** Choose roles/themes in 搜索设置, edit keywords, then start a manual scan. Empty themes disable theme-based exclusions. Search covers Germany nationwide; relocation/notes currently inform optional AI drafting rather than filtering cities.

Run `launch.ps1` in PowerShell to see startup errors; service errors appear in `data/app.log`. Only one installation can use port 48218 at a time.

## Optional schedule

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\schedule.ps1
# Disable without deleting history:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\schedule.ps1 -Remove
```

The task runs as your logged-in Windows user and checks hourly; the app gates scans to weekdays after 18:00 Berlin time, including daylight-saving changes. While open, the app checks every 30 seconds. The lock/completed-batch record prevents duplicate work. Launching after a missed scheduled scan can catch up. Power-off, signed-out users and offline networks cannot fetch jobs. Removing the task also disables automatic scanning inside the app.

## Sources and accuracy

Adapters read Arbeitsagentur public HTML and recognized regional `/jobs?search=` pages with `JobPosting` details. Defaults: bayern.jobs, hessen.jobs, rheinland.jobs, berliner.jobs, hamburger.jobs, jobsfuerniedersachsen.de, maz-job.de, rosinenpicker.de, kuestenfischer.de, suedwest.jobs. This is a catalog, **not a guarantee of current accessibility**.

Custom sources require only name and HTTPS URL; the app tests a search page and one detail before adding. URLs normalize to the site root. Arbitrary sites, JS-only pages, CAPTCHA and changed layouts may be unsupported. Failures are recorded, never treated as zero vacancies. Limits: two pages per keyword, 35 recent detail candidates per source. Coverage is not exhaustive. Exact query terms/links are logged; no hidden fallback queries. Respect site rules; access controls are not bypassed.

Dates, original-date conflicts, work hours and application availability are checked conservatively. Unknown information remains visible. Day-only dates may not prove a strict 24-hour window. Passed checks cannot guarantee eligibility or continued availability.

## Privacy

Settings, histories, CV files/text and logs stay in `data/`. Keys use Windows Credential Manager and are never returned to the browser. The server binds to loopback and requires same-origin requests plus a random token for mutations and CSV export.

CV upload alone is local. Clicking AI analysis sends extracted CV text (up to 30,000 characters) and requirements to OpenAI. Feedback sends job text, your reason, requirements and existing rules, without CV text. API requests set `store:false`; this is not a guarantee of zero provider retention. Deleting local CV files cannot retract data already sent to a provider.

Do not publish CVs, keys, exports, logs or `data/`. Use the allowlisted builder when releasing a copy of an existing installation.

## Development and release

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check web/app.js
# Empty destination outside this tree:
.\.venv\Scripts\python.exe tools/build_release.py --destination ..\job-radar-public --zip ..\job-radar-public.zip
```

Offline tests use synthetic fixtures. CI is configured for Windows/Python 3.11–3.13. The builder copies an explicit allowlist, rejects symlinks and checks obvious secrets/machine paths; review the output before uploading because automated checks cannot detect every secret.

To build the Windows executable, install `requirements-build.txt` in a clean Windows/Python x64 environment, then run `python tools/build_exe.py` and `python tools/smoke_exe.py dist/GermanJobRadar-Windows-x64.exe` (smoke also requires `requirements-dev.txt`). Publishing a GitHub Release triggers the Windows build, offline tests, frozen runtime smoke and asset upload. The spec explicitly bundles web assets, DOCX templates and tzdata; no `data/`, CVs, local settings or keys are bundled.

Implementation: standard-library HTTP server, SQLite snapshots/alias deduplication, lxml parsers, static JS/CSS. Optional AI uses structured Responses API output. Windows-first: native credentials, launch and scheduling are not implemented for Linux/macOS.
