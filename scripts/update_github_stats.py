#!/usr/bin/env python3
"""Generate a self-hosted GitHub statistics card for the profile README."""

from __future__ import annotations

import html
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


USERNAME = os.environ.get("GITHUB_USERNAME", "T-CrB")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "github-stats.svg"
API_ROOT = "https://api.github.com"

LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "C++": "#f34b7d",
    "C": "#555555",
    "Java": "#b07219",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "C#": "#178600",
    "Go": "#00ADD8",
    "Rust": "#dea584",
}


def api_call(path: str, **query: str | int) -> dict | list:
    url = API_ROOT + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "T-CrB-profile-readme/1.0",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def get_repositories() -> list[dict]:
    repositories: list[dict] = []
    page = 1
    while True:
        batch = api_call(
            f"/users/{urllib.parse.quote(USERNAME)}/repos",
            type="owner",
            sort="updated",
            per_page=100,
            page=page,
        )
        if not isinstance(batch, list):
            break
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repositories


def search_count(endpoint: str, query: str) -> int:
    result = api_call(endpoint, q=query, per_page=1)
    return int(result.get("total_count", 0)) if isinstance(result, dict) else 0


def language_breakdown(repositories: list[dict]) -> list[tuple[str, float]]:
    weights: dict[str, float] = {}
    for repository in repositories:
        language = repository.get("language") or "Other"
        weight = max(float(repository.get("size", 1)), 1.0)
        weights[language] = weights.get(language, 0.0) + weight
    total = sum(weights.values()) or 1.0
    return sorted(
        ((language, weight / total * 100) for language, weight in weights.items()),
        key=lambda item: item[1],
        reverse=True,
    )[:6]


def compact_number(number: int) -> str:
    if number >= 1000:
        return f"{number / 1000:.1f}k"
    return str(number)


def build_language_bar(languages: list[tuple[str, float]]) -> tuple[str, str]:
    if not languages:
        return (
            '<rect x="575" y="82" width="330" height="12" rx="6" fill="#30363d"/>',
            '<text x="575" y="125" class="muted">No public language data yet</text>',
        )

    segments: list[str] = []
    legends: list[str] = []
    x = 575.0
    for index, (language, percentage) in enumerate(languages):
        width = 330.0 * percentage / 100.0
        color = LANGUAGE_COLORS.get(language, "#8b949e")
        segments.append(
            f'<rect x="{x:.2f}" y="82" width="{width:.2f}" height="12" fill="{color}"/>'
        )
        column_x = 575 if index % 2 == 0 else 745
        row_y = 125 + (index // 2) * 27
        legends.append(
            f'<circle cx="{column_x}" cy="{row_y - 4}" r="6" fill="{color}"/>'
            f'<text x="{column_x + 12}" y="{row_y}" class="muted">{esc(language)} {percentage:.2f}%</text>'
        )
        x += width
    return "\n".join(segments), "\n".join(legends)


def build_svg(user: dict, repositories: list[dict]) -> str:
    since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    stars = sum(int(repository.get("stargazers_count", 0)) for repository in repositories)
    commits = search_count(
        "/search/commits", f"author:{USERNAME} committer-date:>={since}"
    )
    pull_requests = search_count(
        "/search/issues", f"author:{USERNAME} is:pr created:>={since}"
    )
    issues = search_count(
        "/search/issues", f"author:{USERNAME} is:issue created:>={since}"
    )
    languages = language_breakdown(repositories)
    bar, legends = build_language_bar(languages)
    refreshed = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    metrics = [
        ("Total Stars Earned", stars),
        ("Commits (last year)", commits),
        ("Pull Requests", pull_requests),
        ("Issues", issues),
        ("Public Repositories", int(user.get("public_repos", len(repositories)))),
    ]
    metric_lines = []
    for index, (label, value) in enumerate(metrics):
        y = 113 + index * 25
        metric_lines.append(
            f'<text x="30" y="{y}" class="label">{esc(label)}</text>'
            f'<text x="425" y="{y}" class="value" text-anchor="end">{esc(compact_number(int(value)))}</text>'
        )

    return f'''<!-- Generated by scripts/update_github_stats.py. Do not edit manually. -->
<svg xmlns="http://www.w3.org/2000/svg" width="940" height="250" viewBox="0 0 940 250" role="img" aria-labelledby="title desc">
  <title id="title">GitHub statistics for {esc(USERNAME)}</title>
  <desc id="desc">GitHub activity and most used languages</desc>
  <rect width="940" height="250" rx="10" fill="#0d1117"/>
  <rect x="8" y="8" width="530" height="234" rx="8" fill="#1a1b26"/>
  <rect x="552" y="8" width="380" height="234" rx="8" fill="#1a1b26"/>
  <style>
    .title {{ fill: #70a5fd; font: 700 21px 'Segoe UI', Arial, sans-serif; }}
    .label {{ fill: #38c2b0; font: 600 14px 'Segoe UI', Arial, sans-serif; }}
    .value {{ fill: #f0f6fc; font: 700 15px 'Segoe UI', Arial, sans-serif; }}
    .muted {{ fill: #8b949e; font: 13px 'Segoe UI', Arial, sans-serif; }}
  </style>
  <text x="30" y="48" class="title">{esc(USERNAME)}'s GitHub Stats</text>
  <text x="575" y="48" class="title">Most Used Languages</text>
{chr(10).join(metric_lines)}
  {bar}
  {legends}
  <text x="30" y="229" class="muted">Last refreshed: {esc(refreshed)}</text>
</svg>
'''


def main() -> None:
    user = api_call(f"/users/{urllib.parse.quote(USERNAME)}")
    repositories = get_repositories()
    if not isinstance(user, dict):
        raise RuntimeError("Unexpected GitHub user response")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_svg(user, repositories), encoding="utf-8")
    print(f"Updated {OUTPUT} for {USERNAME}")


if __name__ == "__main__":
    main()
