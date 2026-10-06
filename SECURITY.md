# Security

Local single-user Windows application: do not expose port 48218 through public interfaces, proxies or tunnels. Other processes running as your OS user can access your local files/credentials; this app cannot protect a compromised machine.

Treat JDs, CVs and AI output as untrusted data. Preserve origin/token checks, strict output validation and public-address/redirect URL checks. Keep keys in Windows Credential Manager, never browser state or logs.

Redact private data when reporting issues. Never post live credentials publicly. Prefer repository private vulnerability reporting when available; otherwise privately contact the maintainer before publishing exploit details. No paid bounty or response time is promised.
