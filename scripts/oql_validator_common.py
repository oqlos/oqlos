from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen


def looks_like_html(text: str) -> bool:
    head = text.lstrip()[:500].lower()
    return head.startswith("<!doctype html") or head.startswith("<html")


def extract_code_from_json(data: Any) -> str | None:
    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        if isinstance(data.get("code"), str):
            return data["code"]
        if isinstance(data.get("dsl"), str):
            return data["dsl"]
        scenario = data.get("scenario")
        if isinstance(scenario, dict):
            if isinstance(scenario.get("code"), str):
                return scenario["code"]
            if isinstance(scenario.get("dsl"), str):
                return scenario["dsl"]

    if isinstance(data, list):
        for item in data:
            code = extract_code_from_json(item)
            if code:
                return code

    return None


def fetch_url(url: str, timeout: float = 10.0) -> str:
    req = urlopen(url, timeout=timeout)
    payload = req.read().decode("utf-8", errors="replace")

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload

    code = extract_code_from_json(parsed)
    if code is None:
        return payload
    return code


def build_api_fallback_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    scenario = (query.get("scenario") or [None])[0]
    if not scenario:
        return []

    base = f"{parsed.scheme}://{parsed.netloc}"
    out: list[str] = [
        f"{base}/api/v1/scenarios/{scenario}",
        f"{base}/api/v1/scenarios/{scenario}?{urlencode({'scenario': scenario})}",
        f"{base}/api/v1/scenarios/fetch?{urlencode({'scenario': scenario})}",
    ]

    dedup: list[str] = []
    seen: set[str] = set()
    for item in out:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def load_source(file_path: str | None, url: str | None) -> tuple[str, str]:
    if bool(file_path) == bool(url):
        raise ValueError("Provide exactly one of --file or --url")

    if file_path:
        text = Path(file_path).read_text(encoding="utf-8")
        return text, f"file:{file_path}"

    try:
        source_url = url or ""
        text = fetch_url(source_url)
        if looks_like_html(text):
            for candidate in build_api_fallback_urls(source_url):
                try:
                    candidate_text = fetch_url(candidate)
                except (HTTPError, URLError):
                    continue
                if looks_like_html(candidate_text):
                    continue
                return candidate_text, f"url:{candidate} (fallback from {source_url})"
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Cannot fetch URL {url}: {exc}") from exc
    return text, f"url:{url}"


def run_validator_cli(
    description: str,
    validate: Callable[..., dict[str, Any]],
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--file", help="Path to .oql file")
    parser.add_argument("--url", help="HTTP source with scenario content/code")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON report")
    args = parser.parse_args(argv)

    try:
        text, source = load_source(args.file, args.url)
        report = validate(text, source=source)
    except Exception as exc:
        print(json.dumps({"valid": False, "fatal": str(exc)}, ensure_ascii=False))
        return 2

    if args.pretty:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False))

    return 0 if report.get("valid") else 1
