from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import (
    GetHookdConfigIn,
    MetaAdsConfigIn,
    MetaAdsSearchIngest,
    SimilarwebConfigIn,
    SimilarwebTestIn,
)
from app.core.config import settings
from app.db import models
from app.services.integration_config import (
    IntegrationConfigError,
    delete_meta_credential,
    delete_gethookd_credential,
    delete_similarweb_credential,
    get_meta_credential,
    gethookd_status,
    get_similarweb_credential,
    meta_status,
    save_meta_credential,
    save_gethookd_credential,
    save_similarweb_credential,
    similarweb_status,
)
from app.services.meta_ads import MetaAdsAPIError, effective_meta_fields, search_ads_archive
from app.services.similarweb import SimilarwebClient
from app.utils.security import get_current_user


router = APIRouter()


def _status_contract() -> dict:
    status = similarweb_status()
    status.update(
        {
            "metrics": ["total_visits", "global_rank"],
            "refresh_credit_notice": (
                "A one-month full refresh makes two paid metric requests and normally "
                "uses up to two Similarweb results/data credits. Similarweb controls "
                "entitlements and billing."
            ),
        }
    )
    return status


def _config_error(exc: IntegrationConfigError) -> HTTPException:
    return HTTPException(status_code=500, detail=str(exc))


def _meta_status_contract() -> dict:
    status = meta_status()
    status["coverage_notice"] = (
        "Meta's official API provides political/issue ads worldwide and general ads "
        "delivered to the UK or EU within Meta's published retention window. It does "
        "not provide worldwide commercial-ad coverage."
    )
    return status


@router.get("/gethookd/status")
def get_gethookd_status(_: models.User = Depends(get_current_user)):
    try:
        return gethookd_status()
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc


@router.put("/gethookd/config")
def configure_gethookd(
    payload: GetHookdConfigIn,
    _: models.User = Depends(get_current_user),
):
    try:
        save_gethookd_credential(payload.api_token.get_secret_value())
        return {"saved": True, **gethookd_status()}
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc


@router.delete("/gethookd/config")
def remove_gethookd_config(_: models.User = Depends(get_current_user)):
    try:
        removed = delete_gethookd_credential()
        return {"removed_local_token": removed, **gethookd_status()}
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc


@router.get("/similarweb/status")
def get_similarweb_status(_: models.User = Depends(get_current_user)):
    try:
        return _status_contract()
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc


@router.put("/similarweb/config")
def configure_similarweb(
    payload: SimilarwebConfigIn,
    _: models.User = Depends(get_current_user),
):
    try:
        save_similarweb_credential(payload.api_key.get_secret_value())
        return {"saved": True, **_status_contract()}
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc


@router.delete("/similarweb/config")
def remove_similarweb_config(_: models.User = Depends(get_current_user)):
    try:
        removed = delete_similarweb_credential()
        return {"removed_local_key": removed, **_status_contract()}
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc


@router.post("/similarweb/test")
def test_similarweb(
    payload: SimilarwebTestIn,
    _: models.User = Depends(get_current_user),
):
    """Test both paid metrics without persisting a traffic snapshot."""
    try:
        api_key, _ = get_similarweb_credential()
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc
    if not api_key:
        raise HTTPException(status_code=409, detail="Configure a Similarweb REST API key first")
    with SimilarwebClient(api_key) as client:
        result = client.fetch(
            domain=payload.domain,
            start_date=payload.start_date,
            end_date=payload.end_date,
            country=payload.country,
            main_domain_only=payload.main_domain_only,
        )
    return {
        "ok": result["fetch_status"] == "success",
        "persisted": False,
        "result": result,
        "credit_notice": (
            "This test calls both paid Similarweb endpoints and may consume up to "
            "two results/data credits for each requested month."
        ),
    }


@router.get("/meta/status")
def get_meta_status(_: models.User = Depends(get_current_user)):
    try:
        return _meta_status_contract()
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc


@router.put("/meta/config")
def configure_meta(
    payload: MetaAdsConfigIn,
    _: models.User = Depends(get_current_user),
):
    try:
        save_meta_credential(payload.access_token.get_secret_value())
        return {"saved": True, **_meta_status_contract()}
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc


@router.delete("/meta/config")
def remove_meta_config(_: models.User = Depends(get_current_user)):
    try:
        removed = delete_meta_credential()
        return {"removed_local_token": removed, **_meta_status_contract()}
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc


@router.post("/meta/test")
def test_meta(
    payload: MetaAdsSearchIngest,
    _: models.User = Depends(get_current_user),
):
    """Make a real official API request without persisting its ads."""
    try:
        access_token, _ = get_meta_credential()
    except IntegrationConfigError as exc:
        raise _config_error(exc) from exc
    if not access_token:
        raise HTTPException(status_code=409, detail="Configure a Meta Ad Library access token first")
    try:
        raw_ads = search_ads_archive(
            access_token=access_token,
            ad_reached_countries=payload.ad_reached_countries,
            search_terms=payload.search_terms,
            search_page_ids=payload.search_page_ids,
            ad_type=payload.ad_type,
            ad_active_status=payload.ad_active_status,
            ad_delivery_date_min=payload.ad_delivery_date_min,
            ad_delivery_date_max=payload.ad_delivery_date_max,
            fields=payload.fields,
            limit=payload.limit,
        )
    except MetaAdsAPIError as exc:
        raise HTTPException(status_code=502, detail=exc.as_dict()) from exc
    return {
        "ok": True,
        "persisted": False,
        "provider": "meta_ad_library",
        "source": "official_meta_graph_api",
        "graph_version": settings.meta_graph_version,
        "requested_limit": payload.limit,
        "fetched_count": len(raw_ads),
        "effective_fields": effective_meta_fields(payload.fields),
    }
