import hashlib
import hmac
import logging
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from . import models


router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger("app.payments")


def _flatten_for_signature(data: Dict[str, Any], parent_key: str = "") -> List[Tuple[str, Any]]:
    """
    Prodamus HMAC in PHP typically signs by flattening nested arrays with keys like products[0][name].
    We will approximate by:
    - building key paths like parent[child] for dicts and [index] for lists
    - ignoring None values
    - sorting by key lexicographically before concatenation
    """
    items: List[Tuple[str, Any]] = []
    for key, value in data.items():
        full_key = f"{parent_key}[{key}]" if parent_key else str(key)
        if value is None:
            continue
        if isinstance(value, dict):
            items.extend(_flatten_for_signature(value, full_key))
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                idx_key = f"{full_key}[{idx}]"
                if isinstance(item, dict):
                    items.extend(_flatten_for_signature(item, idx_key))
                else:
                    items.append((idx_key, item))
        else:
            items.append((full_key, value))
    return items


def _create_signature(payload: Dict[str, Any], secret_key: str) -> str:
    # Build sorted key=value string with "::" delimiter like many gateways; adjust if docs require different
    flat = _flatten_for_signature(payload)
    flat.sort(key=lambda kv: kv[0])
    sign_src = ";".join(f"{k}={v}" for k, v in flat)
    digest = hmac.new(secret_key.encode("utf-8"), sign_src.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def build_payform_link(data: Dict[str, Any]) -> str:
    base = settings.payform_url.rstrip("/") + "/"
    # Optionally attach signature if secret configured
    payload = {k: v for k, v in data.items() if v is not None}
    if settings.payform_secret:
        # Build sign src for debug
        try:
            flat = _flatten_for_signature(payload)
            flat.sort(key=lambda kv: kv[0])
            sign_src = ";".join(f"{k}={v}" for k, v in flat)
        except Exception:
            sign_src = ""
        try:
            digest = hmac.new(settings.payform_secret.encode("utf-8"), sign_src.encode("utf-8"), hashlib.sha256).hexdigest()
        except Exception:
            digest = ""
        logger.info(
            "payform.sign: base=%s sys=%s order_id=%s sign_src_len=%s signature=%s",
            base,
            payload.get("sys"),
            payload.get("order_id"),
            len(sign_src or ""),
            digest,
        )
        payload_with_sig = dict(payload)
        payload_with_sig["signature"] = digest
        payload = payload_with_sig
    else:
        pass

    # Build query string manually handling nested structures
    def encode(key: str, value: Any, acc: List[str]):
        from urllib.parse import quote_plus
        if isinstance(value, dict):
            for k, v in value.items():
                encode(f"{key}[{k}]", v, acc)
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                encode(f"{key}[{idx}]", item, acc)
        else:
            acc.append(f"{quote_plus(key)}={quote_plus(str(value))}")

    parts: List[str] = []
    for k, v in payload.items():
        encode(k, v, parts)
    query = "&".join(parts)
    link = f"{base}?{query}" if query else base
    try:
        logger.info(
            "payform.link: url_base=%s query_len=%s preview=%s",
            base,
            len(query),
            (link[:512] + ("..." if len(link) > 512 else "")),
        )
    except Exception:
        pass
    return link


@router.post("/link")
async def create_payment_link(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """
    Create payment link for current user and tariff that was placed in session previously.
    For simplicity, expect JSON body: { "tariff": "subscription"|"single", "podcast_id": optional }
    """
    if not request.session.get("telegram_id"):
        raise HTTPException(status_code=401, detail="unauthorized")

    try:
        body = await request.json()
    except Exception:
        body = {}

    tariff = body.get("tariff")
    podcast_id = body.get("podcast_id")

    user = db.query(models.User).filter(models.User.telegram_id == str(request.session.get("telegram_id"))).first()
    if not user:
        raise HTTPException(status_code=400, detail="user_not_found")

    # Determine items and price
    if tariff == "subscription":
        cfg = db.query(models.AppConfig).first()
        price_cents = (cfg.subscription_price_cents if cfg else 0) or 0
        name = "Подписка"
    elif tariff == "single" and podcast_id:
        pp = db.query(models.PodcastPrice).filter(models.PodcastPrice.podcast_id == int(podcast_id)).first()
        podcast = db.get(models.Podcast, int(podcast_id))
        price_cents = (pp.price_cents if pp else 0) or 0
        name = f"Подкаст: {podcast.title if podcast else podcast_id}"
    else:
        raise HTTPException(status_code=400, detail="bad_tariff")

    # Create pending transaction
    txn = models.Transaction(
        user_id=user.id,
        type="subscription" if tariff == "subscription" else "single",
        podcast_id=int(podcast_id) if tariff == "single" and podcast_id else None,
        status="pending",
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    # Build Payform payload
    rub_amount = max(0, price_cents // 100)
    payload: Dict[str, Any] = {
        "order_id": f"txn-{txn.id}",
        "customer_phone": None,  # let customer fill on payform
        "customer_email": None,
        "products": [
            {
                "name": name,
                "price": rub_amount,
                "quantity": 1,
            }
        ],
        "customer_extra": f"tg:{user.telegram_id}",
        "do": "pay",
        "urlReturn": settings.webapp_url.rstrip("/") + "/failed",
        "urlSuccess": settings.webapp_url.rstrip("/") + "/success",
        "urlNotification": settings.webapp_url.rstrip("/") + "/api/payments/webhook",
        # Attach sys only if configured
        "sys": settings.payform_sys or None,
        # Request JSON response if supported
        # "type": "json",
    }

    # sys is optional for custom integrations
    link = build_payform_link(payload)
    try:
        logger.info(
            "payform.link.created: user_id=%s telegram_id=%s tariff=%s price_rub=%s order_id=%s",
            user.id,
            user.telegram_id,
            tariff,
            rub_amount,
            payload.get("order_id"),
        )
    except Exception:
        pass
    return JSONResponse({"ok": True, "link": link, "txn_id": txn.id})


@router.post("/webhook")
async def payform_webhook(request: Request, db: Session = Depends(get_db), sign: str | None = Header(default=None, alias="Sign")):
    """
    Handle Payform notification. If HMAC secret configured, verify signature using the same
    flattening strategy as for link creation. Expect form-encoded POST.
    """
    try:
        form = await request.form()
        data = {k: v for k, v in form.items()}
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_form")

    if settings.payform_secret:
        if not sign:
            logger.warning("payform.webhook: signature header missing")
            raise HTTPException(status_code=400, detail="signature_missing")
        # Build sign src for webhook data to compare
        try:
            flat = _flatten_for_signature(data)
            flat.sort(key=lambda kv: kv[0])
            sign_src = ";".join(f"{k}={v}" for k, v in flat)
        except Exception:
            sign_src = ""
        calc = hmac.new(settings.payform_secret.encode("utf-8"), sign_src.encode("utf-8"), hashlib.sha256).hexdigest()
        if calc != sign:
            logger.warning(
                "payform.webhook: signature mismatch order_id=%s provided=%s calculated=%s sign_src_len=%s",
                data.get("order_id") or data.get("orderId"),
                sign,
                calc,
                len(sign_src or ""),
            )
            raise HTTPException(status_code=400, detail="signature_incorrect")
        else:
            logger.info("payform.webhook: signature ok order_id=%s", data.get("order_id") or data.get("orderId"))

    order_id = data.get("order_id") or data.get("orderId") or ""
    status_val = str(data.get("status", "")).lower()

    if not order_id or not order_id.startswith("txn-"):
        # Not our order
        return JSONResponse({"ok": True})

    txn_id_str = order_id.split("-", 1)[1]
    try:
        txn_id = int(txn_id_str)
    except Exception:
        return JSONResponse({"ok": True})

    txn = db.get(models.Transaction, txn_id)
    if not txn:
        return JSONResponse({"ok": True})

    if status_val in {"paid", "success", "succeeded"}:
        txn.status = "success"
        if txn.type == "subscription":
            user = db.get(models.User, txn.user_id)
            if user:
                user.has_subscription = True
    elif status_val in {"failed", "error", "canceled", "cancelled"}:
        txn.status = "error"

    db.commit()
    return JSONResponse({"ok": True})


