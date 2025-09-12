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
    Generic flattener (legacy). Kept for reference but not used for Prodamus.
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


def _flatten_prodamus(data: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """
    Prodamus PHP Hmac::create expects PHP-style keys. Based on docs examples:
    - products list is flattened as products[{idx}]name, products[{idx}]price, products[{idx}]quantity
    - nested dicts under product (e.g. tax) use products[{idx}]tax[tax_type]
    - other dicts use bracket notation k[child]
    - None values are skipped
    - Returns list of (key, value) pairs without URL encoding
    """
    pairs: List[Tuple[str, Any]] = []

    def add_pair(k: str, v: Any):
        if v is None:
            return
        pairs.append((k, v))

    for key, value in data.items():
        if value is None:
            continue
        if key == "products" and isinstance(value, list):
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    for pkey, pval in item.items():
                        if pval is None:
                            continue
                        if isinstance(pval, dict):
                            # products[{idx}]tax[tax_type]=...
                            for sk, sv in pval.items():
                                if sv is None:
                                    continue
                                add_pair(f"products[{idx}][{pkey}][{sk}]", sv)
                        else:
                            # products[{idx}]name=..., price=..., quantity=...
                            add_pair(f"products[{idx}][{pkey}]", pval)
                else:
                    # non-dict product element (unlikely)
                    add_pair(f"products[{idx}]", item)
        elif isinstance(value, dict):
            # generic dict -> k[child]
            for sk, sv in value.items():
                if sv is None:
                    continue
                if isinstance(sv, dict):
                    for ssk, ssv in sv.items():
                        if ssv is None:
                            continue
                        add_pair(f"{key}[{sk}][{ssk}]", ssv)
                elif isinstance(sv, list):
                    for sidx, sitem in enumerate(sv):
                        add_pair(f"{key}[{sk}][{sidx}]", sitem)
                else:
                    add_pair(f"{key}[{sk}]", sv)
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                add_pair(f"{key}[{idx}]", item)
        else:
            add_pair(str(key), value)

    return pairs


def _flatten_prodamus_php_style(data: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """
    PHP-style flattener: products[0]name (not products[0][name])
    """
    pairs: List[Tuple[str, Any]] = []

    def add_pair(k: str, v: Any):
        if v is None:
            return
        pairs.append((k, v))

    for key, value in data.items():
        if value is None:
            continue
        if key == "products" and isinstance(value, list):
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    for pkey, pval in item.items():
                        if pval is None:
                            continue
                        if isinstance(pval, dict):
                            # products[{idx}]tax[tax_type]=...
                            for sk, sv in pval.items():
                                if sv is None:
                                    continue
                                add_pair(f"products[{idx}]{pkey}[{sk}]", sv)
                        else:
                            # products[{idx}]name=..., price=..., quantity=... (PHP style)
                            add_pair(f"products[{idx}]{pkey}", pval)
                else:
                    # non-dict product element (unlikely)
                    add_pair(f"products[{idx}]", item)
        elif isinstance(value, dict):
            # generic dict -> k[child]
            for sk, sv in value.items():
                if sv is None:
                    continue
                if isinstance(sv, dict):
                    for ssk, ssv in sv.items():
                        if ssv is None:
                            continue
                        add_pair(f"{key}[{sk}][{ssk}]", ssv)
                elif isinstance(sv, list):
                    for sidx, sitem in enumerate(sv):
                        add_pair(f"{key}[{sk}][{sidx}]", sitem)
                else:
                    add_pair(f"{key}[{sk}]", sv)
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                add_pair(f"{key}[{idx}]", item)
        else:
            add_pair(str(key), value)

    return pairs


def _create_signature(payload: Dict[str, Any], secret_key: str) -> str:
    # Prodamus compatibility: sort by key, join as key=value with '&' like querystring but without URL encoding
    flat = _flatten_prodamus(payload)
    flat.sort(key=lambda kv: kv[0])
    sign_src = "&".join(f"{k}={v}" for k, v in flat)
    digest = hmac.new(secret_key.encode("utf-8"), sign_src.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def build_payform_link(data: Dict[str, Any]) -> str:
    base = settings.payform_url.rstrip("/") + "/"
    payload = {k: v for k, v in data.items() if v is not None}

    # Signature first: raw flattened pairs (without URL encoding), keys like products[0]name
    sign_src = ""
    digest = ""
    if settings.payform_secret:
        try:
            # Exclude URL routing params from signature (often not included by provider)
            sign_payload = {k: v for k, v in payload.items() if k not in {"urlReturn", "urlSuccess", "urlNotification", "signature"}}
            # Use PHP-style keys: products[0]name (not products[0][name])
            flat_for_sign = _flatten_prodamus_php_style(sign_payload)
            # Build sign source with raw values (no URL encoding)
            sign_src = "&".join(f"{k}={v}" for k, v in flat_for_sign)
            digest = hmac.new(settings.payform_secret.encode("utf-8"), sign_src.encode("utf-8"), hashlib.sha256).hexdigest()
            payload["signature"] = digest
            try:
                logger.info("payform.sign.keys: %s", [k for k, _ in flat_for_sign])
            except Exception:
                pass
        except Exception:
            pass

    # Now build final query including signature using same flattened keys but URL-encoded
    from urllib.parse import quote_plus
    flat_pairs = _flatten_prodamus(payload)
    query_parts: List[str] = []
    for k, v in flat_pairs:
        query_parts.append(f"{quote_plus(str(k))}={quote_plus(str(v))}")
    query = "&".join(query_parts)
    link = f"{base}?{query}" if query else base
    try:
        logger.info(
            "payform.sign: base=%s order_id=%s sign_src_len=%s signature=%s",
            base,
            payload.get("order_id"),
            len(sign_src or ""),
            digest,
        )
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
        # Build sign src for webhook data to compare using the same strategy
        try:
            flat = _flatten_prodamus(data)
            flat.sort(key=lambda kv: kv[0])
            sign_src = "&".join(f"{k}={v}" for k, v in flat)
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


