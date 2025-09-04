from fastapi import APIRouter, Request, Depends, Header
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
    init_data: str,
    db: Session = Depends(get_db),
):
    parsed = validate_init_data(init_data, bot_token=settings.bot_token)
    if not parsed or "user" not in parsed:
        return JSONResponse({"ok": False}, status_code=400)

    tg_user = parsed["user"]
    telegram_id = str(tg_user.get("id"))
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        user = models.User(telegram_id=telegram_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    request.session["telegram_id"] = telegram_id
    return {"ok": True}


