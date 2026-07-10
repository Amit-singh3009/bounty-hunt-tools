# Bounty Hunt Tools

Small Python tooling for finding safer open-source bounty candidates on GitHub.

The scanner is intentionally conservative. It rejects issues that look noisy, already claimed, assigned, created by security bots, or already covered by open pull requests.

## Why

Many public bounty issues attract duplicate low-quality pull requests. This tool helps avoid wasting maintainer time and protects contributor reputation.

## Usage

Prerequisites:

- Python 3.10+
- GitHub CLI installed and authenticated with `gh auth login`

```powershell
python bounty_scanner.py --limit 100
```

The scan writes:

```text
candidates.md
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
