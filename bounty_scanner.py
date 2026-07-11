import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


NOISY_REPOS = {
    "xevrion-v2/agent-playground",
    "SecureBananaLabs/bug-bounty",
    "coopfinance/coopfin-frontend",
    "cocohub-mobileapp/cocohub-main",
    "NSPG13/agent-bounties",
    "Scottcjn/rustchain-bounties",
    "verdikta/verdikta-applications",
    "verdikta/verdikta-docs",
    "devpool-directory/devpool-directory",
}

NOISY_TITLE_WORDS = (
    "bounty alert",
    "bounty claim",
    "daily issue report",
    "daily report",
    "agent competition",
    "zero-bounty",
    "high-priority",
    "good first issues",
    "vulnerabilities",
    "vulnerability",
    "highest severity",
    ".whl",
    ".tar.gz",
    "dependency",
)

ADVANCED_TITLE_WORDS = (
    "base sepolia",
    "directed bounty",
    "on-chain",
    "evm",
    "merkle",
    "quorum",
    "smart-account",
    "rust",
    "go]",
    "[go]",
    "slither",
    "brownie",
)

NOISY_LABEL_WORDS = (
    "mend",
    "security",
    "vulnerability",
    "dependency",
    "feedback",
    "bounty-feeback",
)

BOUNTY_LABEL_WORDS = (
    "bounty",
    "price:",
    "reward",
    "usd",
    "paid",
)

CLAIM_WORDS = (
    "claiming this",
    "i'm claiming",
    "i am claiming",
    "assign this issue to me",
    "assigned.",
    "assigned to",
    "submitted pr",
    "opened pr",
    "implemented in:",
    "the fix for",
    "not accepting new",
    "won't accept new",
    "will not accept new",
    "already attempting",
    "has been awarded",
    "/claim",
)


def gh_api(path: str) -> dict:
    proc = subprocess.run(
        ["gh", "api", path],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return json.loads(proc.stdout)


def search_issues(query: str, limit: int) -> list[dict]:
    per_page = min(max(limit, 1), 100)
    path = f"search/issues?q={quote(query)}&sort=updated&order=desc&per_page={per_page}"
    return gh_api(path).get("items", [])


def repo_from_api_url(url: str) -> str:
    return url.removeprefix("https://api.github.com/repos/")


def has_open_collision(repo: str, issue_number: int, issue_title: str) -> tuple[bool, str]:
    prs = gh_api(f"repos/{repo}/pulls?state=open&per_page=50")
    issue_ref = f"#{issue_number}"
    title_words = [
        word
        for word in re.findall(r"[a-z0-9_]+", issue_title.lower())
        if len(word) > 5 and word not in {"bugfix", "feature", "enhance"}
    ][:6]

    for pr in prs:
        pr_title = (pr.get("title") or "").lower()
        branch = (pr.get("head", {}).get("ref") or "").lower()
        if issue_ref in pr_title or str(issue_number) in branch:
            return True, pr.get("html_url", "")
        matching_words = sum(1 for word in title_words if word in pr_title)
        if title_words and matching_words >= min(3, len(title_words)):
            return True, pr.get("html_url", "")
    return False, ""


def has_claim_comment(repo: str, issue_number: int) -> tuple[bool, str]:
    comments = gh_api(f"repos/{repo}/issues/{issue_number}/comments?per_page=20")
    for comment in comments:
        body = (comment.get("body") or "").lower()
        if any(word in body for word in CLAIM_WORDS):
            return True, comment.get("html_url", "")
    return False, ""


def score_candidate(item: dict, repo: dict, collision: bool) -> int:
    score = 100
    score -= int(item.get("comments", 0)) * 12
    score += min(int(repo.get("stargazers_count", 0)), 200) // 20
    score += min(int(repo.get("forks_count", 0)), 100) // 25
    if repo.get("fork"):
        score -= 40
    if collision:
        score -= 60
    updated = item.get("updated_at", "")
    if updated.startswith("2026"):
        score += 15
    elif updated.startswith("2025"):
        score += 5
    else:
        score -= 50
    return score


def label_text(item: dict) -> str:
    return " ".join(label.get("name", "") for label in item.get("labels", [])).lower()


def is_noisy_issue(item: dict, repo_name: str) -> bool:
    title_lower = (item.get("title") or "").lower()
    labels_lower = label_text(item)
    if repo_name in NOISY_REPOS:
        return True
    if any(word in title_lower for word in NOISY_TITLE_WORDS):
        return True
    if any(word in title_lower for word in ADVANCED_TITLE_WORDS):
        return True
    if any(word in labels_lower for word in NOISY_LABEL_WORDS):
        return True
    return False


def has_bounty_signal(item: dict) -> bool:
    labels_lower = label_text(item)
    title_lower = (item.get("title") or "").lower()
    return any(word in labels_lower or word in title_lower for word in BOUNTY_LABEL_WORDS)


def build_report(candidates: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Bounty Candidate Report",
        "",
        f"Generated: {now}",
        "",
        "This report filters for JavaScript, TypeScript, and Python issues with bounty/good-first-issue signals, then penalizes crowded issues, stale repos, forks, and open PR collisions.",
        "",
    ]

    if not candidates:
        lines.append("No safe candidates found in this scan.")
        return "\n".join(lines) + "\n"

    if not any(not candidate["collision"] for candidate in candidates):
        lines.extend(
            [
                "No unclaimed candidates found in this scan. The entries below are kept only as audit notes so we know what was rejected.",
                "",
            ]
        )

    for idx, c in enumerate(candidates, 1):
        status = "skip: open PR collision" if c["collision"] else "possible"
        lines.extend(
            [
                f"## {idx}. {c['title']}",
                "",
                f"- Status: {status}",
                f"- Score: {c['score']}",
                f"- Repo: `{c['repo']}` ({c['language'] or 'unknown'}, stars {c['stars']}, forks {c['forks']})",
                f"- Issue: {c['url']}",
                f"- Comments: {c['comments']}",
                f"- Labels: {c['labels'] or 'none'}",
            ]
        )
        if c["collision_url"]:
            lines.append(f"- Collision PR: {c['collision_url']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out", default="candidates.md")
    args = parser.parse_args()

    queries = [
        'is:issue is:open label:bounty label:"good first issue" comments:<4 language:TypeScript',
        'is:issue is:open label:bounty label:"good first issue" comments:<4 language:JavaScript',
        'is:issue is:open label:bounty label:"good first issue" comments:<4 language:Python',
        'is:issue is:open "/bounty $" comments:<4 TypeScript',
        'is:issue is:open "/bounty $" comments:<4 Python',
    ]

    seen = set()
    candidates = []

    for query in queries:
        for item in search_issues(query, args.limit):
            if "pull_request" in item:
                continue

            repo_name = repo_from_api_url(item["repository_url"])
            title = item.get("title", "")
            if is_noisy_issue(item, repo_name):
                continue
            if not has_bounty_signal(item):
                continue
            key = (repo_name, item["number"])
            if key in seen:
                continue
            seen.add(key)

            if item.get("assignee") or item.get("assignees"):
                continue

            repo = gh_api(f"repos/{repo_name}")
            repo_lang = repo.get("language")
            if repo_lang not in {"JavaScript", "TypeScript", "Python"}:
                continue
            updated_at = item.get("updated_at", "")
            if not (updated_at.startswith("2026") or updated_at.startswith("2025")):
                continue
            collision, collision_url = has_open_collision(repo_name, item["number"], title)
            claimed, claim_url = has_claim_comment(repo_name, item["number"])
            if claimed:
                collision = True
                collision_url = collision_url or claim_url
            labels = ", ".join(label["name"] for label in item.get("labels", []))
            candidate = {
                "repo": repo_name,
                "title": title,
                "url": item["html_url"],
                "comments": item.get("comments", 0),
                "labels": labels,
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language"),
                "collision": collision,
                "collision_url": collision_url,
            }
            candidate["score"] = score_candidate(item, repo, collision)
            candidates.append(candidate)

    candidates.sort(key=lambda c: c["score"], reverse=True)
    report = build_report(candidates[:20])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote {out_path}")
    possible_candidates = [candidate for candidate in candidates if not candidate["collision"]]
    if possible_candidates:
        best = possible_candidates[0]
        print(f"Best: {best['repo']} - {best['title']} ({best['score']})")
    elif candidates:
        print("No unclaimed candidates found; report contains only skip candidates.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
