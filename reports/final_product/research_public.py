"""Bounded read-only public repository evidence; never executes repository content."""

import asyncio
import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

REPOS = (
    "freqtrade/freqtrade",
    "hummingbot/hummingbot",
    "jesse-ai/jesse",
    "Drakkar-Software/OctoBot",
    "mementum/backtrader",
    "polakowo/vectorbt",
    "Pouryazv/nobitex-moving-average-trader",
    "alimogh/BBK-Nobitex-Robot",
    "dwin-gharibi/ramzinex-mcp",
    "moazeniz/wallex-ai-trader",
)


async def main():
    semaphore = asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=True) as http:

        async def one(repo):
            async with semaphore:
                result = {"repo": repo, "accessed_utc": datetime.now(UTC).isoformat()}
                for suffix in (
                    "",
                    "/commits?per_page=1",
                    "/readme",
                    "/issues?state=all&labels=bug&per_page=2",
                ):
                    key = {
                        "": "metadata",
                        "/readme": "readme",
                        "/commits?per_page=1": "commit",
                    }.get(suffix, "issues")
                    try:
                        response = await http.get("https://api.github.com/repos/" + repo + suffix)
                        result[key + "_http"] = response.status_code
                        if response.status_code != 200:
                            continue
                        body = response.json()
                        if key == "metadata":
                            result[key] = {
                                k: body.get(k)
                                for k in (
                                    "html_url",
                                    "description",
                                    "archived",
                                    "pushed_at",
                                    "updated_at",
                                    "default_branch",
                                    "license",
                                )
                            }
                        elif key == "commit":
                            result[key] = [
                                {"sha": b["sha"], "date": b["commit"]["committer"]["date"]}
                                for b in body
                            ]
                        elif key == "readme":
                            text = base64.b64decode(body["content"]).decode(
                                "utf-8", errors="replace"
                            )
                            result[key] = {
                                "html_url": body.get("html_url"),
                                "git_blob_sha": body.get("sha"),
                                "headings": [
                                    line[:150] for line in text.splitlines() if line.startswith("#")
                                ][:25],
                            }
                        else:
                            result[key] = [
                                {
                                    "url": b["html_url"],
                                    "title": b["title"],
                                    "state": b["state"],
                                    "created_at": b["created_at"],
                                }
                                for b in body
                                if "pull_request" not in b
                            ]
                    except (httpx.HTTPError, ValueError, KeyError):
                        result[key + "_error"] = (
                            "Public retrieval unavailable; no inference of absence"
                        )
                return result

        results = await asyncio.gather(*(one(repo) for repo in REPOS))
    path = Path("reports/final_product/repository_evidence.json")
    with path.open("x", encoding="utf-8") as stream:
        json.dump(results, stream, indent=2, ensure_ascii=True)
    print(json.dumps(results, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    asyncio.run(main())
