import ipaddress
import socket
import time
from threading import Lock
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import settings
from app.utils.urls import normalize_public_url


_robots_cache: dict[str, RobotFileParser] = {}
_last_fetch_by_domain: dict[str, float] = {}
_rate_lock = Lock()
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5


class UnsafeDestination(ValueError):
    """Raised when DNS or a redirect points outside the public internet."""


class ResponseTooLarge(ValueError):
    """Raised before an untrusted response can consume unbounded memory."""


def validate_public_destination(url: str) -> str:
    """Normalize a URL and reject any hostname resolving to a non-global IP."""

    try:
        normalized = normalize_public_url(url)
    except ValueError as exc:
        raise UnsafeDestination(str(exc)) from exc
    parsed = urlparse(normalized)
    hostname = parsed.hostname
    if not hostname:
        raise UnsafeDestination("A public hostname is required")
    try:
        rows = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise OSError(f"Could not resolve public hostname {hostname}") from exc
    if not rows:
        raise OSError(f"Could not resolve public hostname {hostname}")

    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for row in rows:
        raw_address = str(row[4][0]).split("%", 1)[0]
        try:
            addresses.add(ipaddress.ip_address(raw_address))
        except ValueError as exc:
            raise UnsafeDestination("DNS returned an invalid address") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise UnsafeDestination(
            "Private, local, reserved, and otherwise non-public destinations cannot be scanned"
        )
    return normalized


def _respect_rate_limit(domain: str) -> None:
    now = time.time()
    with _rate_lock:
        last = _last_fetch_by_domain.get(domain, 0.0)
        allowed_at = max(now, last + settings.crawl_min_interval_seconds)
        _last_fetch_by_domain[domain] = allowed_at
    delay = allowed_at - now
    if delay > 0:
        time.sleep(delay)


def request_public_url(
    client: httpx.Client,
    url: str,
    *,
    timeout: int,
    rate_limit: bool = True,
    max_bytes: int | None = None,
) -> tuple[httpx.Response, str]:
    """GET a public URL while validating DNS and every redirect destination."""

    current = url
    response_limit = max_bytes or settings.max_response_bytes
    for redirect_count in range(_MAX_REDIRECTS + 1):
        current = validate_public_destination(current)
        if rate_limit:
            _respect_rate_limit(urlparse(current).netloc.lower())
        with client.stream(
            "GET",
            current,
            timeout=timeout,
            follow_redirects=False,
        ) as streamed:
            status_code = streamed.status_code
            headers = streamed.headers
            request = streamed.request
            location = headers.get("location")
            if status_code not in _REDIRECT_STATUSES or not location:
                declared_size = headers.get("content-length")
                if declared_size and declared_size.isdigit() and int(declared_size) > response_limit:
                    raise ResponseTooLarge(
                        f"Response exceeded the {response_limit}-byte collection limit"
                    )
                chunks: list[bytes] = []
                received = 0
                for chunk in streamed.iter_bytes():
                    received += len(chunk)
                    if received > response_limit:
                        raise ResponseTooLarge(
                            f"Response exceeded the {response_limit}-byte collection limit"
                        )
                    chunks.append(chunk)
                copied_headers = [
                    (name, value)
                    for name, value in headers.multi_items()
                    if name.lower()
                    not in {"content-encoding", "content-length", "transfer-encoding"}
                ]
                copied_headers.append(("content-length", str(received)))
                response = httpx.Response(
                    status_code,
                    headers=copied_headers,
                    content=b"".join(chunks),
                    request=request,
                    extensions=streamed.extensions,
                )
                return response, current
        if redirect_count >= _MAX_REDIRECTS:
            raise httpx.TooManyRedirects(
                "Public URL exceeded the five-redirect safety limit",
                request=request,
            )
        current = urljoin(current, location)
    raise RuntimeError("Unreachable redirect state")


def _get_robot_parser(url: str) -> RobotFileParser:
    normalized = validate_public_destination(url)
    parsed_url = urlparse(normalized)
    cache_key = f"{parsed_url.scheme}://{parsed_url.netloc.lower()}"
    if cache_key in _robots_cache:
        return _robots_cache[cache_key]

    robots_url = f"{cache_key}/robots.txt"
    parser = RobotFileParser()
    try:
        with httpx.Client(headers={"User-Agent": settings.user_agent}) as client:
            response, _ = request_public_url(
                client,
                robots_url,
                timeout=10,
                max_bytes=1_000_000,
            )
        parser.parse(response.text.splitlines() if response.status_code < 400 else [])
    except UnsafeDestination:
        raise
    except Exception:
        # A missing/unreachable robots file is treated as no published rules.
        parser.parse([])
    _robots_cache[cache_key] = parser
    return parser


def fetch_url(url: str, timeout: int = 20) -> Tuple[Optional[str], Optional[str], int]:
    try:
        normalized = validate_public_destination(url)
        parser = _get_robot_parser(normalized)
    except UnsafeDestination:
        return None, None, 403
    except Exception:
        return None, None, 500

    if not parser.can_fetch(settings.user_agent, normalized):
        return None, None, 403

    with httpx.Client(headers={"User-Agent": settings.user_agent}) as client:
        for attempt in range(3):
            try:
                response, final_url = request_public_url(
                    client,
                    normalized,
                    timeout=timeout,
                )
                if response.status_code >= 400:
                    return None, final_url, response.status_code
                return response.text, final_url, response.status_code
            except UnsafeDestination:
                return None, None, 403
            except ResponseTooLarge:
                return None, None, 413
            except Exception:
                if attempt == 2:
                    return None, None, 500
                time.sleep(1 + attempt)
    return None, None, 500
