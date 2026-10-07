# German Job Radar

A local Windows app for finding jobs in Germany with your own keywords, reading captured job descriptions and exporting results to CSV. The interface is Chinese; German and English job content is preserved.

[中文使用说明](docs/USAGE.zh-CN.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT license](LICENSE)

## Download and start

1. Download [GermanJobRadar-Windows-x64.zip](https://github.com/ZzzGenjicat/german-job-radar/releases/latest/download/GermanJobRadar-Windows-x64.zip).
2. Extract the ZIP and double-click **GermanJobRadar-Windows-x64.exe**. Your default browser opens the local app.
3. Replace the example keywords, choose job types in **搜索设置**, then click **搜索近24小时新岗**.

Windows 10/11 x64. No Python installation or administrator access is required. First launch does not search. The executable is unsigned. See [Windows instructions](docs/WINDOWS.md) for updates and troubleshooting.

## What it does

- Search regular jobs, internships and working-student roles. Full-time is an optional filter. New installations have no fixed AI/CRM direction filter.
- Edit, enable or remove keywords. For regular jobs, use terms such as `Buchhaltung` or `CRM`; an `Intern` prefix narrows the website's search to internships.
- Optionally expand keywords once using a local terminology map: a related term must appear in two distinct candidate JDs. At most ten additions, with evidence, take effect on the next scan. Deleted or renamed terms are not automatically restored. No API key is needed.
- Review two lists: **待人工筛查** (manual screening) and **已排除** (excluded). Cards retain publication evidence, captured text and exclusion reasons. “New only” compares against this installation's history.
- Export both complete lists to an Excel-friendly CSV, including jobs hidden by “new only”. Stable job numbers match the dashboard. The CSV is marked **只作为建议** (suggestions only).
- Open job and application links in the OS default browser.

## Automatic searches

In **搜索设置 → 自动搜索**, enable scheduling, choose a time and save. The default is **18:00, Monday–Friday, Europe/Berlin**. The app and Windows Task Scheduler run it locally; no Codex or ChatGPT session is needed.

The PC must be on, online and signed in. Closing the browser does not stop scheduling. Missed searches can catch up for the current workday; a completed automatic search is not repeated that day, even after changing the time. Daytime manual scans remain available. Keep the EXE at a fixed location, or save scheduling settings again after moving it.

## Sources and limits

Built-in adapters cover Arbeitsagentur public HTML and recognized regional job boards. Add a source by name and HTTPS URL; the app tests a search page and a detail page before accepting it. Arbitrary websites, CAPTCHAs and changed layouts may be unsupported.

Reads are limited to two pages per keyword and 35 recent detail candidates per source. Failures are shown, not treated as zero vacancies. Coverage is not exhaustive. First discovery is not publication time; date-only entries and missing information remain flagged. Automated checks cannot guarantee suitability or continued availability. Check the original JD before applying.

## Optional AI and privacy

Search, local keyword expansion and CSV export work without AI. CV-based keyword drafts and feedback analysis require your own OpenAI API key and may incur charges. A ChatGPT subscription does not include an API key. AI proposals affect keywords or filtering only after your confirmation.

Settings, history, CVs and logs stay in `%LOCALAPPDATA%\GermanJobRadar`. Uploading a CV extracts text locally. Clicking AI analysis sends CV text (up to 30,000 characters) and search requirements to OpenAI. Feedback analysis sends job text, your reason, requirements and saved rules, without CV text. Requests use `store:false`; provider retention policies may still apply. Deleting local files cannot retract already-sent data.

Keys use Windows Credential Manager. The server binds to loopback with origin/token checks. Do not publish local app data, credentials, CVs or personal exports. Technical setup, tests and release instructions are in [CONTRIBUTING.md](CONTRIBUTING.md).
