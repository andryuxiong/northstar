import ipaddress
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def normalize_public_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("A URL is required")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a valid public HTTP or HTTPS URL")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise ValueError("Only public storefront URLs can be scanned")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValueError("Private or local network addresses cannot be scanned")
    netloc = f"[{hostname}]" if address and address.version == 6 else hostname
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    safe_query = urlencode(
        [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in {"access_token", "appsecret_proof"}
        ],
        doseq=True,
    )
    return urlunparse((parsed.scheme, netloc, parsed.path or "/", "", safe_query, ""))
