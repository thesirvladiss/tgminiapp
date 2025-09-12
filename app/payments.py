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
                                add_pair(f"products[{idx}]{pkey}[{sk}]", sv)
                        else:
                            # products[{idx}][name]=..., price=..., quantity=...
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


def _create_signature(payload: Dict[str, Any], secret_key: str) -> str:
    # 1) Берём все поля, кроме signature
    data = {k: v for k, v in payload.items() if k != "signature" and v is not None}
    # 2) Плосим PHP-стилем (products[0][name], ...)
    flat = _flatten_prodamus(data)
    # 3) Сортируем по ключу
    flat.sort(key=lambda kv: kv[0])
    # 4) Склеиваем С url-энкодингом (как в итоговой ссылке)
    from urllib.parse import quote_plus
    sign_src = "&".join(f"{quote_plus(str(k))}={quote_plus(str(v))}" for k, v in flat)
    # 5) HMAC-SHA256 в hex
    return hmac.new(secret_key.encode("utf-8"), sign_src.encode("utf-8"), hashlib.sha256).hexdigest()


def build_payform_link(data: Dict[str, Any]) -> str:
    base = settings.payform_url.rstrip("/") + "/"
    payload = {k: v for k, v in data.items() if v is not None}

    # МИНИМУМ: только обязательные поля для подписи
    if settings.payform_secret:
        # Только основные поля без URL-параметров
        min_payload = {
            "do": payload.get("do"),
            "order_id": payload.get("order_id"),
            "products": payload.get("products")
        }
        
        # Простые ключи без скобок
        sign_parts = []
        sign_parts.append(f"do={min_payload['do']}")
        sign_parts.append(f"order_id={min_payload['order_id']}")
        
        # Продукты в простом формате
        for i, product in enumerate(min_payload['products']):
            sign_parts.append(f"products[{i}][name]={product['name']}")
            sign_parts.append(f"products[{i}][price]={product['price']}")
            sign_parts.append(f"products[{i}][quantity]={product['quantity']}")
        
        sign_src = "&".join(sign_parts)
        digest = hmac.new(settings.payform_secret.encode("utf-8"), sign_src.encode("utf-8"), hashlib.sha256).hexdigest()
        payload["signature"] = digest
        
        logger.info("payform.sign.minimal: %s", sign_src)
        logger.info("payform.signature: %s", digest)

    # Собираем финальный query уже с url-энкодингом (это ок — подпись считали до энкодинга)
    from urllib.parse import quote_plus
    flat_pairs = _flatten_prodamus(payload)
    query = "&".join(f"{quote_plus(str(k))}={quote_plus(str(v))}" for k, v in flat_pairs)
    link = f"{base}?{query}" if query else base

    try:
        logger.info("payform.sign: base=%s order_id=%s signature=%s", base, payload.get("order_id"), payload.get("signature"))
        logger.info("payform.link: preview=%s", (link[:512] + ("..." if len(link) > 512 else "")))
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
    try:
        form = await request.form()
        # form уже плоский (ключи вида products[0][name]); это нормально.
        data = {k: v for k, v in form.items()}
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_form")

    if settings.payform_secret:
        if not sign:
            logger.warning("payform.webhook: signature header missing")
            raise HTTPException(status_code=400, detail="signature_missing")

        # ВАЖНО: считаем тем же способом, что и при формировании ссылки
        calc = _create_signature(data, settings.payform_secret)
        if calc != sign:
            logger.warning(
                "payform.webhook: signature mismatch order_id=%s provided=%s calculated=%s",
                data.get("order_id") or data.get("orderId"),
                sign,
                calc,
            )
            raise HTTPException(status_code=400, detail="signature_incorrect")
        else:
            logger.info("payform.webhook: signature ok order_id=%s", data.get("order_id") or data.get("orderId"))

