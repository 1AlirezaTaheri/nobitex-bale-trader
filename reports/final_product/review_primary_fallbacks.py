"""Best-effort Latin PDF literal review, not a general PDF parser or replication."""

import asyncio
import hashlib
import json
import re
import zlib
from datetime import UTC, datetime
from pathlib import Path

import httpx

SOURCES = {
    "R1-author": "https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf",
    "R3-author": "https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf",
    "R4-author": "https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf",
    "R5-nber": "https://www.nber.org/system/files/working_papers/w22208/w22208.pdf",
    "R6-original-mirror": "https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf",
    "R8-author": "https://web.stanford.edu/~wfsharpe/art/dyn/dyn.htm",
    "R9-issuer": "https://corporate.vanguard.com/content/dam/corp/research/pdf/cost_averaging_invest_now_or_temporarily_hold_your_cash.pdf",
    "R11-author": "https://thierry-roncalli.com/download/erc.pdf",
    "R12-nber": "https://www.nber.org/system/files/working_papers/w24877/w24877.pdf",
    "R13-author": "https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/individual_investor_performance_final.pdf",
    "R16-issuer": "https://www.wellsfargoadvisors.com/research-analysis/reports/digital-assets/digital-asset-volatility.htm",
    "nobitex-market": "https://apidocs.nobitex.ir/market_data/",
}


def literal_text(data):
    pieces = []
    for stream in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            decoded = zlib.decompress(stream[1])
        except zlib.error:
            decoded = stream[1]
        for block in re.findall(rb"\bBT\b(.*?)\bET\b", decoded, re.S):
            line = []
            for token in re.findall(rb"\(((?:\\.|[^\\)])*)\)", block, re.S):
                token = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m[1], 8) % 256]), token)
                token = re.sub(rb"\\([()\\])", rb"\1", token)
                line.append(token.decode("cp1252", errors="replace"))
            if line:
                pieces.append("".join(line))
    return " ".join(pieces)


async def main():
    semaphore = asyncio.Semaphore(2)
    async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=True) as client:

        async def one(key, url):
            async with semaphore:
                record = {"source": key, "url": url, "accessed_utc": datetime.now(UTC).isoformat()}
                try:
                    response = await client.get(url)
                    record.update(
                        status=response.status_code,
                        sha256=hashlib.sha256(response.content).hexdigest(),
                    )
                    if response.status_code != 200:
                        return record
                    if response.content.startswith(b"%PDF"):
                        text = literal_text(response.content)
                        record["extraction"] = (
                            "Partial literal-text only; missing fonts/math/layout; not full PDF review"
                        )
                    else:
                        text = re.sub(
                            r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>",
                            " ",
                            response.text,
                            flags=re.S,
                        )
                        text = re.sub("<[^>]+>", " ", text)
                        record["extraction"] = "HTML text"
                    text = re.sub(r"\s+", " ", text)
                    record["readable_characters"] = len(text)
                    if key == "R16-issuer":
                        at = text.find("83%")
                        excerpt = text[max(0, at - 1200) : at + 2400]
                    else:
                        at = text.lower().find("abstract")
                        excerpt = text[max(0, at) : max(0, at) + 5200]
                    print(json.dumps({"source": key, "review_excerpt": excerpt}, ensure_ascii=True))
                except (httpx.HTTPError, ValueError):
                    record["retrieval"] = "UNVERIFIED"
                return record

        records = await asyncio.gather(*(one(k, url) for k, url in SOURCES.items()))
    with Path("reports/final_product/primary_fallback_evidence.json").open(
        "x", encoding="utf-8"
    ) as stream:
        json.dump(records, stream, indent=2)
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
