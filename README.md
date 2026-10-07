# German Job Radar

A local Windows dashboard for German job searches. Use your own keywords, inspect captured job descriptions and evidence, and export an Excel-friendly CSV. The interface is currently Chinese; German and English job content is preserved.

[中文说明](docs/USAGE.zh-CN.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT license](LICENSE)

## Download for Windows — no Python required

Download [GermanJobRadar-Windows-x64.zip](https://github.com/ZzzGenjicat/german-job-radar/releases/latest/download/GermanJobRadar-Windows-x64.zip), extract it and double-click the EXE. Or download the [standalone EXE](https://github.com/ZzzGenjicat/german-job-radar/releases/latest/download/GermanJobRadar-Windows-x64.exe). Windows 10/11 x64; no administrator or Python installation needed. See [Windows instructions](docs/WINDOWS.md), license notices and SHA256 checksums in [Releases](https://github.com/ZzzGenjicat/german-job-radar/releases).

The bundled app saves data in `%LOCALAPPDATA%\GermanJobRadar`, independent of the EXE's location. Exit in the dashboard before replacing the EXE; history stays. Enable automatic searches and choose a time in search settings (default 18:00 Europe/Berlin, Monday–Friday). Keep the EXE at a fixed location, or save scheduling settings again after moving it. The executable is currently unsigned.

## Features

- Regular employment, internships and/or working-student roles. Full-time is a separate option; turn it off to accept part-time. Junior is allowed unless you add it to exclusions.
- Editable keywords, optional themes and exclusion words. Initial AI/CRM terms are examples, not fixed restrictions. For regular jobs, use broad terms such as `Buchhaltung` or `CRM` without an `Intern` prefix.
- Optional **local first-scan expansion** from an inspectable terminology map. A related term must appear in at least two distinct eligible JDs. At most ten additions, with evidence, used on the **next** scan. Deleted or renamed terms are blocked from automatic re-addition. No API key/cloud request.
- Two lists: **待人工筛查** (manual screening) and **已排除** (excluded). Cards distinguish passed checks from evidence gaps. Human judgement is still required.
- Manual rolling 24-hour scans; optional weekday searches at a user-selected time (default 18:00 Europe/Berlin). Scheduling runs locally without Codex, even with the browser closed. Later scans default to unseen jobs. First discovery is not publication time.
- Stable batch-wide numbers. CSV exports **both complete lists**, including records hidden by “new only”, with the title `德国岗位雷达（只作为建议）` and a separate column-header row. Numbers match the dashboard.
- Links open in the OS default browser. No automatic applications, bookmarks, Google Drive or spreadsheet sync.
- Optional local PDF/DOCX extraction and OpenAI keyword drafting/feedback analysis. AI drafts require your confirmation, your own API key and may incur charges. A ChatGPT subscription is not an API key.

## Getting started

1. Download the named **GermanJobRadar-Windows-x64.zip** asset from [Releases](https://github.com/ZzzGenjicat/german-job-radar/releases/latest).
2. Extract the ZIP and double-click **GermanJobRadar-Windows-x64.exe**. Your default browser opens the local app.
3. Choose roles/themes in **搜索设置**, edit your keywords, then start a manual scan. **First launch does not search.**

No Python installation, terminal commands or dependency setup is needed. Empty themes disable theme-based exclusions. Search covers Germany nationwide; relocation/notes currently inform optional AI drafting rather than filtering cities. See [Windows instructions](docs/WINDOWS.md) for updates and troubleshooting.

## Optional schedule

In **搜索设置 → 自动搜索**, tick **开启自动搜索**, choose an HH:MM time, and click **保存自动搜索设置**. Untick and save to disable; the chosen time is preserved. The default is 18:00, Monday–Friday, in Germany's timezone rather than your PC's timezone.

Windows Task Scheduler runs as your logged-in user and wakes at the selected minute of each hour; the app gates scans to weekdays after the chosen Berlin time, including daylight-saving changes. While running, the app checks every 30 seconds. No Codex or ChatGPT session is needed. The lock/completed-batch record prevents duplicate scans on the same day, even after changing the time. Manual daytime scans do not cancel the scheduled scan. Saving an already-past time or launching after a missed scan can catch up for the current workday. Power-off, signed-out users and offline networks cannot fetch jobs. Removing the task also disables automatic scanning inside the app.

## Sources and accuracy

Adapters read Arbeitsagentur public HTML and recognized regional `/jobs?search=` pages with `JobPosting` details. Defaults: bayern.jobs, hessen.jobs, rheinland.jobs, berliner.jobs, hamburger.jobs, jobsfuerniedersachsen.de, maz-job.de, rosinenpicker.de, kuestenfischer.de, suedwest.jobs. This is a catalog, **not a guarantee of current accessibility**.

Custom sources require only name and HTTPS URL; the app tests a search page and one detail before adding. URLs normalize to the site root. Arbitrary sites, JS-only pages, CAPTCHA and changed layouts may be unsupported. Failures are recorded, never treated as zero vacancies. Limits: two pages per keyword, 35 recent detail candidates per source. Coverage is not exhaustive. Exact query terms/links are logged; no hidden fallback queries. Respect site rules; access controls are not bypassed.

Dates, original-date conflicts, work hours and application availability are checked conservatively. Unknown information remains visible. Day-only dates may not prove a strict 24-hour window. Passed checks cannot guarantee eligibility or continued availability.

## Privacy

Settings, histories, CV files/text and logs stay in `%LOCALAPPDATA%\GermanJobRadar`. Keys use Windows Credential Manager and are never returned to the browser. The server binds to loopback and requires same-origin requests plus a random token for mutations and CSV export.

CV upload alone is local. Clicking AI analysis sends extracted CV text (up to 30,000 characters) and requirements to OpenAI. Feedback sends job text, your reason, requirements and existing rules, without CV text. API requests set `store:false`; this is not a guarantee of zero provider retention. Deleting local CV files cannot retract data already sent to a provider.

Do not publish CVs, keys, exports, logs or your local app data.

## Contributing

Code contributors can find development, testing and release instructions in [CONTRIBUTING.md](CONTRIBUTING.md). The ready-to-run Windows download includes its runtime and dependencies.
