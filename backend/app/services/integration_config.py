import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings


PLAINTEXT_STORAGE_WARNING = (
    "The Similarweb API key is stored unencrypted in a local file on this computer. "
    "Do not share or sync that file, and use SIMILARWEB_API_KEY instead if you need "
    "credential storage managed outside Northstar."
)

META_PLAINTEXT_STORAGE_WARNING = (
    "The Meta access token is stored unencrypted in a local file on this computer. "
    "Do not share or sync that file, and use META_ADS_ACCESS_TOKEN instead if you "
    "need credential storage managed outside Northstar."
)

GETHOOKD_PLAINTEXT_STORAGE_WARNING = (
    "The GetHookd API token is stored unencrypted in a local file on this computer. "
    "Do not share or sync that file, and use GETHOOKD_API_TOKEN instead if you "
    "need credential storage managed outside Northstar."
)


class IntegrationConfigError(RuntimeError):
    pass


def _config_path() -> Path:
    return Path(settings.integration_config_path).expanduser().resolve()


def _read_config() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationConfigError(f"Could not read local integration settings: {exc}") from exc
    if not isinstance(payload, dict):
        raise IntegrationConfigError("The local integration settings file is not a JSON object")
    return payload


def _write_config(payload: dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        try:
            temporary.chmod(0o600)
        except OSError:
            # Windows chmod does not guarantee an exclusive ACL. The API status
            # deliberately exposes that this remains plaintext local storage.
            pass
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise IntegrationConfigError(f"Could not save local integration settings: {exc}") from exc


def mask_secret(secret: str) -> str:
    if len(secret) <= 4:
        return "•" * len(secret)
    return f"{'•' * 8}{secret[-4:]}"


def get_similarweb_credential() -> tuple[str | None, str | None]:
    """Return the active key and its source without ever logging the key."""
    environment_key = settings.similarweb_api_key.strip()
    if environment_key:
        return environment_key, "environment"
    config = _read_config()
    similarweb = config.get("similarweb")
    if isinstance(similarweb, dict):
        api_key = similarweb.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip(), "local_file"
    return None, None


def save_similarweb_credential(api_key: str) -> None:
    api_key = api_key.strip()
    if not api_key:
        raise IntegrationConfigError("A non-empty Similarweb API key is required")
    config = _read_config()
    config["similarweb"] = {
        "api_key": api_key,
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    _write_config(config)


def delete_similarweb_credential() -> bool:
    config = _read_config()
    existed = "similarweb" in config
    config.pop("similarweb", None)
    if config:
        _write_config(config)
    else:
        try:
            _config_path().unlink(missing_ok=True)
        except OSError as exc:
            raise IntegrationConfigError(f"Could not remove local integration settings: {exc}") from exc
    return existed


def similarweb_status() -> dict[str, Any]:
    api_key, source = get_similarweb_credential()
    return {
        "provider": "similarweb",
        "configured": bool(api_key),
        "active_source": source,
        "masked_key": mask_secret(api_key) if api_key else None,
        "local_config_path": str(_config_path()),
        "storage": "environment" if source == "environment" else "plaintext_local_file",
        "storage_warning": PLAINTEXT_STORAGE_WARNING,
        "data_notice": (
            "Similarweb visits and rank are provider estimates, not a store's "
            "first-party analytics or exact live visitors."
        ),
    }


def get_meta_credential() -> tuple[str | None, str | None]:
    """Return the active Meta token and its source without exposing it in status."""
    environment_token = settings.meta_ads_access_token.strip()
    if environment_token:
        return environment_token, "environment"
    config = _read_config()
    meta = config.get("meta")
    if isinstance(meta, dict):
        token = meta.get("access_token")
        if isinstance(token, str) and token.strip():
            return token.strip(), "local_file"
    return None, None


def save_meta_credential(access_token: str) -> None:
    token = access_token.strip()
    if not token:
        raise IntegrationConfigError("A non-empty Meta access token is required")
    config = _read_config()
    config["meta"] = {
        "access_token": token,
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    _write_config(config)


def delete_meta_credential() -> bool:
    config = _read_config()
    existed = "meta" in config
    config.pop("meta", None)
    if config:
        _write_config(config)
    else:
        try:
            _config_path().unlink(missing_ok=True)
        except OSError as exc:
            raise IntegrationConfigError(f"Could not remove local integration settings: {exc}") from exc
    return existed


def meta_status() -> dict[str, Any]:
    access_token, source = get_meta_credential()
    return {
        "provider": "meta_ad_library",
        "source": "official_meta_graph_api",
        "configured": bool(access_token),
        "active_source": source,
        "masked_token": mask_secret(access_token) if access_token else None,
        "graph_version": settings.meta_graph_version,
        "local_config_path": str(_config_path()),
        "storage": "environment" if source == "environment" else "plaintext_local_file",
        "storage_warning": META_PLAINTEXT_STORAGE_WARNING,
        "data_notice": (
            "Results are public records returned by Meta's official Ad Library API. "
            "Northstar does not scrape the Meta UI or fabricate spend, reach, or traffic metrics. "
            "Provider snapshot URLs are converted to public Ad Library permalinks so an "
            "embedded access token is never stored."
        ),
    }


def get_gethookd_credential() -> tuple[str | None, str | None]:
    """Return the active GetHookd token without exposing it to the frontend."""
    environment_token = settings.gethookd_api_token.strip()
    if environment_token:
        return environment_token, "environment"
    config = _read_config()
    gethookd = config.get("gethookd")
    if isinstance(gethookd, dict):
        token = gethookd.get("api_token")
        if isinstance(token, str) and token.strip():
            return token.strip(), "local_file"
    return None, None


def save_gethookd_credential(api_token: str) -> None:
    token = api_token.strip()
    if not token:
        raise IntegrationConfigError("A non-empty GetHookd API token is required")
    config = _read_config()
    config["gethookd"] = {
        "api_token": token,
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    _write_config(config)


def delete_gethookd_credential() -> bool:
    config = _read_config()
    existed = "gethookd" in config
    config.pop("gethookd", None)
    if config:
        _write_config(config)
    else:
        try:
            _config_path().unlink(missing_ok=True)
        except OSError as exc:
            raise IntegrationConfigError(f"Could not remove local integration settings: {exc}") from exc
    return existed


def gethookd_status() -> dict[str, Any]:
    api_token, source = get_gethookd_credential()
    return {
        "provider": "gethookd",
        "source": "gethookd_public_api",
        "configured": bool(api_token),
        "active_source": source,
        "masked_token": mask_secret(api_token) if api_token else None,
        "local_config_path": str(_config_path()),
        "storage": "environment" if source == "environment" else "plaintext_local_file",
        "storage_warning": GETHOOKD_PLAINTEXT_STORAGE_WARNING,
        "credit_notice": (
            "GetHookd search/list endpoints consume provider credits based on results returned. "
            "Northstar shows the provider-reported credit usage after each search."
        ),
        "data_notice": (
            "GetHookd records and classifications are imported provider data. Ad duration, "
            "activity, and provider scores do not prove spend, conversions, ROAS, or profit."
        ),
    }
