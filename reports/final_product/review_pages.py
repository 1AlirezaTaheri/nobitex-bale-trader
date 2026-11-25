"""Read-only primary-page review; persist retrieval metadata, not copyrighted articles."""

import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

URLS = {
    "R1": "https://www.sciencedirect.com/science/article/pii/S0304405X11002613",
    "R2": "https://www.sciencedirect.com/science/article/pii/S1386418116301379",
    "R3": "https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf",
    "R4": "https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf",
    "R5": "https://www.nber.org/papers/w22208",
    "R6": "https://ieeexplore.ieee.org/abstract/document/6771227",
    "R7": "https://www.sciencedirect.com/science/article/pii/S0304405X2030132X",
    "R8": "https://caia.org/sites/default/files/dynamic_strategies_for_asset_allocation.pdf",
    "R9": "https://corporate.vanguard.com/content/dam/corp/research/pdf/cost_averaging_invest_now_or_temporarily_hold_your_cash.pdf",
    "R10": "https://www.math.nyu.edu/~chriss/optliq_f.pdf",
    "R11": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1271972",
    "R12": "https://www.nber.org/papers/w24877",
    "R13": "https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00226",
    "R14": "https://www.bis.org/publ/bisbull69.htm",
    "R15": "https://www.sec.gov/Archives/edgar/data/1980994/000143774923035270/bit20231221_s1a.htm",
    "R16": "https://www.wellsfargoadvisors.com/research-analysis/reports/digital-assets/digital-asset-volatility.htm",
    "nobitex_start": "https://apidocs.nobitex.ir/getting-started",
    "ms_wake": "https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-waketorun",
    "ms_delayed": "https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-startwhenavailable",
}


async def main():
    limit = asyncio.Semaphore(4)
    async with httpx.AsyncClient(timeout=18, trust_env=False, follow_redirects=True) as client:

        async def one(key, url):
            async with limit:
                record = {"id": key, "url": url, "accessed_utc": datetime.now(UTC).isoformat()}
                try:
                    response = await client.get(url)
                    record.update(
                        status=response.status_code,
                        final_url=str(response.url),
                        sha256=hashlib.sha256(response.content).hexdigest(),
                    )
                    if response.status_code != 200:
                        return record
                    if response.content.startswith(b"%PDF"):
                        # PyMuPDF is already installed; never install a parser in this review.
                        import fitz

                        with fitz.open(stream=response.content, filetype="pdf") as document:
                            text = " ".join(
                                document[i].get_text() for i in range(min(3, len(document)))
                            )
                    else:
                        text = re.sub(
                            r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>",
                            " ",
                            response.text,
                            flags=re.S,
                        )
                        text = re.sub("<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text)
                    record["text_characters_reviewed"] = len(text)
                    print(json.dumps({"id": key, "review_excerpt": text[:1800]}, ensure_ascii=True))
                    record["terms"] = {
                        term: term in text.lower()
                        for term in (
                            "momentum",
                            "drawdown",
                            "77%",
                            "83%",
                            "iran",
                            "abstract",
                            "bitcoin",
                        )
                    }
                except (httpx.HTTPError, ValueError, ImportError):
                    record["retrieval"] = "UNVERIFIED; unavailable or PDF parser absent"
                return record

        records = await asyncio.gather(*(one(k, url) for k, url in URLS.items()))
    with Path("reports/final_product/primary_page_evidence.json").open(
        "x", encoding="utf-8"
    ) as stream:
        json.dump(records, stream, indent=2)
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
