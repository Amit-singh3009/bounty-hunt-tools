# Bounty Hunt Tools

Small Python tooling for finding safer open-source bounty candidates on GitHub.

The scanner is intentionally conservative. It rejects issues that look noisy, already claimed, assigned, security-bot generated, or already covered by open pull requests.

## Why

Many public bounty issues attract duplicate low-quality pull requests. This tool helps avoid wasting maintainer time and protects contributor reputation.

## Usage

```powershell
cd C:\Users\akrk1\Documents\Eris
& "C:\Users\akrk1\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" bounty_hunt\bounty_scanner.py --limit 100
```

The scan writes:

```text
bounty_hunt/candidates.md
```

## Current Filters

- JavaScript, TypeScript, and Python repositories
- Recent open issues only
- Bounty or reward signal required
- Skips automated dependency vulnerability issues
- Skips assigned issues
- Skips issues with claim comments
- Skips issues with likely open PR collisions

## Principle

Do not submit duplicate PRs. A clean GitHub reputation is more valuable than forcing a low-quality attempt.
