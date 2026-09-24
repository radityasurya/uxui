# Security Policy

## Supported Versions

Only the latest `main` branch of this plugin receives security fixes.

| Version | Supported |
|---------|-----------|
| Latest `main` | ✅ |
| Older releases | ❌ |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report it privately using [GitHub's private vulnerability reporting](https://github.com/radityasurya/uxui/security/advisories/new) (Security tab → "Report a vulnerability").

Include as much of the following as possible:

- A description of the vulnerability and its potential impact
- Steps to reproduce (command, prompt, or skill invocation used)
- The plugin version and the AI assistant/platform involved
- Any relevant logs or output

We aim to acknowledge reports within 5 business days and to provide a fix or mitigation timeline within 14 days for confirmed issues.

## Scope

This project is a design-data and recommendation plugin: Python search scripts and static data (CSV/JSON) consumed by AI coding assistants. In-scope concerns include:

- Arbitrary code execution via the bundled search or generator scripts
- Path traversal or unsafe file writes when running the bundled scripts

Out of scope: the design output itself (colors, fonts, UI recommendations) is not a security surface.
