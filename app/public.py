import logging
from fastapi import APIRouter, Request, Depends, Header, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .database import get_db
from .telegram_utils import validate_init_data
from .config import settings
from . import models

router = APIRouter(prefix="/api")


@router.post("/telegram/auth")
def telegram_auth(
    request: Request,
    init_data: str = Form(...),
    db: Session = Depends(get_db),
):
    logger = logging.getLogger("app.telegram")
    ua = request.headers.get("user-agent", "")
    ref = request.headers.get("referer", "")
    origin = request.headers.get("origin", "")
    logger.info(
        "telegram_auth called: ua=%s ref=%s origin=%s init_data_len=%s snippet=%s",
        ua,
        ref,
        origin,
        len(init_data or ""),
        (init_data or "")[:200],
    )

    parsed = validate_init_data(init_data, bot_token=settings.bot_token)
    if not parsed or "user" not in parsed:
        logger.warning("telegram_auth validation failed")
        return JSONResponse({"ok": False}, status_code=400)

    tg_user = parsed["user"]
    telegram_id = str(tg_user.get("id"))
    logger.info("telegram_auth success: telegram_id=%s", telegram_id)
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        user = models.User(telegram_id=telegram_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    request.session["telegram_id"] = telegram_id
    return {"ok": True}


