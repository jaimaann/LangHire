# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | Yes                |
| < 1.0   | No                 |

Only the latest release receives security updates.

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, use one of these private channels:

1. **GitHub Security Advisories** (preferred): Go to the [Security tab](https://github.com/jaimaann/LangHire/security/advisories) and click "Report a vulnerability"
2. **Email**: Contact the maintainer directly via GitHub profile

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response timeline

- **Acknowledgment**: Within 72 hours
- **Initial assessment**: Within 1 week
- **Fix release**: Depends on severity (critical: ASAP, high: 1-2 weeks, medium/low: next release)

## Scope

The following are considered security issues:

- API token leakage or bypass of authentication middleware
- Credential exposure (LLM API keys, browser session cookies, user passwords)
- Unauthorized access to the browser profile or stored data
- Server-Side Request Forgery (SSRF) via job URLs
- Remote code execution through crafted inputs
- Path traversal in resume file handling

The following are NOT security issues (file as regular bugs):

- Rate limiting bypass on localhost-only endpoints
- Denial of service on a single-user desktop app
- UI rendering issues
