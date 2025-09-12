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


def build_payform_link(data: Dict[str, Any]) -> str:
    """
    Строим ссылку на оплату по документации Продамуса.
    Минимальный набор: do, products, order_id
    """
    base = settings.payform_url.rstrip("/") + "/"
    
    # Минимальный набор параметров
    payload = {
        "do": data.get("do", "pay"),
        "order_id": data.get("order_id"),
        "products": data.get("products", [])
    }
    
    # Добавляем опциональные параметры если есть
    if data.get("customer_phone"):
        payload["customer_phone"] = data["customer_phone"]
    if data.get("customer_email"):
        payload["customer_email"] = data["customer_email"]
    if data.get("customer_extra"):
        payload["customer_extra"] = data["customer_extra"]
    if data.get("urlReturn"):
        payload["urlReturn"] = data["urlReturn"]
    if data.get("urlSuccess"):
        payload["urlSuccess"] = data["urlSuccess"]
    if data.get("urlNotification"):
        payload["urlNotification"] = data["urlNotification"]
    if data.get("sys"):
        payload["sys"] = data["sys"]
    
    # Если есть секрет - добавляем подпись
    if settings.payform_secret:
        signature = create_signature(payload, settings.payform_secret)
        payload["signature"] = signature
        logger.info("payform.signature: %s", signature)
    
    # Строим query string
    from urllib.parse import urlencode
    query_parts = []
    
    # Обрабатываем products отдельно (нужны скобки)
    for key, value in payload.items():
        if key == "products":
            for i, product in enumerate(value):
                query_parts.append(f"products[{i}][name]={product['name']}")
                query_parts.append(f"products[{i}][price]={product['price']}")
                query_parts.append(f"products[{i}][quantity]={product['quantity']}")
        else:
            query_parts.append(f"{key}={value}")
    
    query = "&".join(query_parts)
    link = f"{base}?{query}"
    
    logger.info("payform.link: %s", link[:200] + "..." if len(link) > 200 else link)
    return link


def create_signature(payload: Dict[str, Any], secret_key: str) -> str:
    """
    Создаем подпись по документации Продамуса.
    Сортируем параметры по ключу, исключаем signature, склеиваем через &
    """
    # Исключаем signature из подписи
    sign_data = {k: v for k, v in payload.items() if k != "signature"}
    
    # Сортируем по ключу
    sorted_keys = sorted(sign_data.keys())
    
    # Собираем строку для подписи
    sign_parts = []
    for key in sorted_keys:
        value = sign_data[key]
        if key == "products":
            # Обрабатываем products отдельно
            for i, product in enumerate(value):
                sign_parts.append(f"products[{i}][name]={product['name']}")
                sign_parts.append(f"products[{i}][price]={product['price']}")
                sign_parts.append(f"products[{i}][quantity]={product['quantity']}")
        else:
            sign_parts.append(f"{key}={value}")
    
    sign_string = "&".join(sign_parts)
    logger.info("payform.sign_string: %s", sign_string)
    
    # HMAC-SHA256
    signature = hmac.new(
        secret_key.encode("utf-8"),
        sign_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return signature


@router.post("/link")
async def create_payment_link(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Создаем ссылку на оплату"""
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

    # Определяем товар и цену
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

    # Создаем транзакцию
    txn = models.Transaction(
        user_id=user.id,
        type="subscription" if tariff == "subscription" else "single",
        podcast_id=int(podcast_id) if tariff == "single" and podcast_id else None,
        status="pending",
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    # Строим данные для платежки
    rub_amount = max(0, price_cents // 100)
    payment_data = {
        "do": "pay",
        "order_id": f"txn-{txn.id}",
        "order_sum": rub_amount,  # Сумма заказа
        "products": [
            {
                "name": name,
                "price": rub_amount,
                "quantity": 1,
            }
        ],
        "customer_extra": f"tg:{user.telegram_id}",
        "urlReturn": settings.webapp_url.rstrip("/") + "/failed",
        "urlSuccess": settings.webapp_url.rstrip("/") + "/success",
        "urlNotification": settings.webapp_url.rstrip("/") + "/api/payments/webhook",
        # Дополнительные параметры для корректной работы
        "currency": "rub",  # Валюта платежа
        "type": "json",     # Ответ в JSON формате
        "callbackType": "json",  # Webhook в JSON формате
    }
    
    # Добавляем sys если настроен
    if settings.payform_sys:
        payment_data["sys"] = settings.payform_sys

    link = build_payform_link(payment_data)
    return JSONResponse({"ok": True, "link": link, "txn_id": txn.id})


@router.post("/webhook")
async def payform_webhook(
    request: Request, 
    db: Session = Depends(get_db), 
    sign: str | None = Header(default=None, alias="Sign")
):
    """Обрабатываем уведомления от Продамуса"""
    # Пробуем получить JSON, если не получается - form data
    try:
        data = await request.json()
        logger.info("payform.webhook: received JSON data: %s", data)
    except Exception:
        try:
            form = await request.form()
            data = {k: v for k, v in form.items()}
            logger.info("payform.webhook: received form data: %s", data)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_data")

    # Проверяем подпись если настроен секрет
    if settings.payform_secret:
        if not sign:
            logger.warning("payform.webhook: signature header missing")
            raise HTTPException(status_code=400, detail="signature_missing")
        
        # Считаем подпись
        calc_signature = create_signature(data, settings.payform_secret)
        if calc_signature != sign:
            logger.warning(
                "payform.webhook: signature mismatch order_id=%s provided=%s calculated=%s",
                data.get("order_id"),
                sign,
                calc_signature,
            )
            raise HTTPException(status_code=400, detail="signature_incorrect")
        else:
            logger.info("payform.webhook: signature ok order_id=%s", data.get("order_id"))

    # Обрабатываем заказ
    order_id = data.get("order_id") or data.get("orderId") or ""
    status_val = str(data.get("status", "")).lower()

    if not order_id or not order_id.startswith("txn-"):
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
