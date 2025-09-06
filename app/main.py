import logging
import sys
import time
from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from fastapi.exceptions import RequestValidationError

from .database import Base, engine, get_db
from . import models
from .auth import router as auth_router
from .admin import router as admin_router
from .config import settings
from .public import router as public_router


ACCESS_LOGGER_NAME = "app.access"
HTTP_LOGGER_NAME = "app.http"
ERROR_LOGGER_NAME = "app.errors"


def _headers_dump(request: Request, limit: int = 50) -> dict:
    """Безопасный дамп заголовков с нижним регистром ключей."""
    try:
        return {k.lower(): (v if len(v) <= 4096 else v[:4096] + "...") for k, v in request.headers.items()}
    except Exception:
        return {}

def _body_snippet(body: bytes, limit: int = 2048) -> str:
    if not body:
        return ""
    if len(body) > limit:
        return body[:limit].decode("utf-8", errors="replace") + "..."
    return body.decode("utf-8", errors="replace")


def create_app() -> FastAPI:
    # Configure logging for app.* loggers to stdout
    root_logger = logging.getLogger()
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    app = FastAPI(title="PL Mini App")

    # Mount static and uploads
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    templates = Jinja2Templates(directory="templates")

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Session middleware for admin auth
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    # --- ЛОГИРОВАНИЕ: middleware доступа и тела запроса ---
    access_logger = logging.getLogger(ACCESS_LOGGER_NAME)
    http_logger = logging.getLogger(HTTP_LOGGER_NAME)
    error_logger = logging.getLogger(ERROR_LOGGER_NAME)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        Единый access-лог: метод, путь, статус, время, ip, длины, заголовки (сниппет),
        плюс сниппет тела для интересных эндпоинтов.
        """
        start = time.perf_counter()
        client_ip = request.client.host if request.client else "-"
        ua = request.headers.get("user-agent", "")
        ref = request.headers.get("referer", "")
        origin = request.headers.get("origin", "")
        xff = request.headers.get("x-forwarded-for", "")

        # считать тело безопасно: Starlette кэширует его и дальше form()/json() будет работать
        raw_body = b""
        try:
            # Логируем тело только для POST/PUT/PATCH/DELETE и только для наших внутренних путей,
            # чтобы не зашумлять логи
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                raw_body = await request.body()
        except Exception as e:
            error_logger.debug("failed to read request body: %r", e)

        headers_dump = _headers_dump(request)

        # Узкий таргет: развёрнутый сниппет показываем для auth и checkout
        body_for_log = ""
        if request.url.path in {"/api/telegram/auth", "/checkout"}:
            body_for_log = _body_snippet(raw_body, limit=2048)

        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:
            # Неловленные исключения тоже логируем
            duration_ms = int((time.perf_counter() - start) * 1000)
            error_logger.exception(
                "unhandled exception: method=%s path=%s ip=%s xff=%s ua=%s ref=%s origin=%s "
                "dur_ms=%s headers=%s body_snippet=%s",
                request.method, request.url.path, client_ip, xff, ua, ref, origin,
                duration_ms, headers_dump, body_for_log
            )
            # Пробрасываем дальше, чтобы сработал глобальный error handler FastAPI
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        http_logger.info(
            "access: %s %s -> %s (%sms) ip=%s xff=%s ua=%s ref=%s origin=%s clen=%s headers=%s body_snippet=%s",
            request.method,
            request.url.path,
            status,
            duration_ms,
            client_ip,
            xff,
            ua,
            ref,
            origin,
            request.headers.get("content-length", "-"),
            headers_dump,
            body_for_log,
        )
        return response

    # --- ЛОГИРОВАНИЕ: обработчики ошибок валидации/400 ---
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        body = b""
        try:
            body = await request.body()
        except Exception:
            pass
        error_logger.warning(
            "422 validation error: path=%s headers=%s body=%s errors=%s",
            request.url.path,
            _headers_dump(request),
            _body_snippet(body, 2048),
            exc.errors(),
        )
        return JSONResponse({"detail": exc.errors()}, status_code=422)

    # Routers
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(public_router)

    def _require_telegram(request: Request):
        if not request.session.get("telegram_id"):
            logging.getLogger(ACCESS_LOGGER_NAME).info(
                "no telegram_id in session: path=%s, ip=%s, ua=%s, ref=%s, origin=%s",
                request.url.path,
                getattr(request.client, "host", "-"),
                request.headers.get("user-agent", ""),
                request.headers.get("referer", ""),
                request.headers.get("origin", ""),
            )
            return templates.TemplateResponse("front/loader.html", {"request": request})
        return None

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, db: Session = Depends(get_db)):
        if not request.session.get("telegram_id"):
            logging.getLogger(ACCESS_LOGGER_NAME).info(
                "home blocked, no telegram_id: ip=%s ua=%s",
                getattr(request.client, "host", "-"),
                request.headers.get("user-agent", ""),
            )
            return templates.TemplateResponse("front/loader.html", {"request": request})
        cards = (
            db.query(models.ProjectCard)
            .order_by(models.ProjectCard.order.asc(), models.ProjectCard.id.asc())
            .all()
        )
        return templates.TemplateResponse(
            "front/index.html", {"request": request, "cards": cards}
        )

    @app.get("/podcasts", response_class=HTMLResponse)
    def podcast_list(request: Request, db: Session = Depends(get_db)):
        if not request.session.get("telegram_id"):
            logging.getLogger(ACCESS_LOGGER_NAME).info(
                "podcasts blocked, no telegram_id: ip=%s ua=%s",
                getattr(request.client, "host", "-"),
                request.headers.get("user-agent", ""),
            )
            return templates.TemplateResponse("front/loader.html", {"request": request})
        podcasts = (
            db.query(models.Podcast)
            .filter(models.Podcast.is_published.is_(True))
            .order_by(models.Podcast.published_at.desc())
            .all()
        )
        return templates.TemplateResponse(
            "front/podcasts.html", {"request": request, "podcasts": podcasts}
        )

    @app.get("/podcasts/{podcast_id}", response_class=HTMLResponse)
    def podcast_detail(
        podcast_id: int,
        request: Request,
        preview: int | None = None,
        db: Session = Depends(get_db),
    ):
        if not request.session.get("telegram_id"):
            logging.getLogger(ACCESS_LOGGER_NAME).info(
                "podcast_detail blocked, no telegram_id: ip=%s ua=%s",
                getattr(request.client, "host", "-"),
                request.headers.get("user-agent", ""),
            )
            return templates.TemplateResponse("front/loader.html", {"request": request})
        podcast = db.get(models.Podcast, podcast_id)
        if not podcast:
            return RedirectResponse("/podcasts")

        user = _get_or_create_user(request, db)
        has_access = _user_has_full_access(user, podcast, db)

        audio_src = (
            podcast.audio_full_path if has_access and podcast.audio_full_path else None
        )

        return templates.TemplateResponse(
            "front/podcasts-details.html",
            {
                "request": request,
                "podcast": podcast,
                "has_access": has_access,
                "audio_src": audio_src,
            },
        )

    @app.get("/free-issue", response_class=HTMLResponse)
    def free_issue(podcast_id: int, request: Request, db: Session = Depends(get_db)):
        if not request.session.get("telegram_id"):
            logging.getLogger(ACCESS_LOGGER_NAME).info(
                "free_issue blocked, no telegram_id: ip=%s ua=%s",
                getattr(request.client, "host", "-"),
                request.headers.get("user-agent", ""),
            )
            return templates.TemplateResponse("front/loader.html", {"request": request})
        podcast = db.get(models.Podcast, podcast_id)
        if not podcast:
            return RedirectResponse("/podcasts")
        return templates.TemplateResponse(
            "front/free-issue.html", {"request": request, "podcast": podcast}
        )

    @app.get("/checkout", response_class=HTMLResponse)
    def checkout(podcast_id: int | None = None, request: Request = None):
        if request and not request.session.get("telegram_id"):
            logging.getLogger(ACCESS_LOGGER_NAME).info(
                "checkout blocked, no telegram_id: ip=%s ua=%s",
                getattr(request.client, "host", "-"),
                request.headers.get("user-agent", ""),
            )
            return templates.TemplateResponse("front/loader.html", {"request": request})
        # Prices: subscription + selected podcast price
        from . import models
        from sqlalchemy.orm import Session
        db_sess: Session | None = None
        try:
            db_sess = get_db().__next__()
            cfg = db_sess.query(models.AppConfig).first()
            sub_price_rub = int(((cfg.subscription_price_cents if cfg else 0) or 0) / 100)
            single_price_rub = 0
            if podcast_id:
                pp = db_sess.query(models.PodcastPrice).filter(models.PodcastPrice.podcast_id == podcast_id).first()
                single_price_rub = int(((pp.price_cents if pp else 0) or 0) / 100)
        except Exception:
            sub_price_rub = 0
            single_price_rub = 0
        finally:
            try:
                if db_sess:
                    db_sess.close()
            except Exception:
                pass

        return templates.TemplateResponse(
            "front/subscription.html",
            {"request": request, "podcast_id": podcast_id, "sub_price_rub": sub_price_rub, "single_price_rub": single_price_rub},
        )

    @app.post("/checkout")
    def do_checkout(
        request: Request,
        db: Session = Depends(get_db),
        tariff: str = Form(...),  # 'subscription' or 'single'
        podcast_id: int | None = Form(None),
    ):
        if not request.session.get("telegram_id"):
            logging.getLogger(ACCESS_LOGGER_NAME).info(
                "do_checkout blocked, no telegram_id: ip=%s ua=%s",
                getattr(request.client, "host", "-"),
                request.headers.get("user-agent", ""),
            )
            return templates.TemplateResponse("front/loader.html", {"request": request})
        user = _get_or_create_user(request, db)
        if not user:
            return RedirectResponse("/", status_code=302)

        if tariff == "subscription":
            user.has_subscription = True
            txn = models.Transaction(user_id=user.id, type="subscription", status="success")
            db.add(txn)
            db.commit()
            return RedirectResponse("/success", status_code=302)

        if tariff == "single" and podcast_id:
            txn = models.Transaction(
                user_id=user.id, type="single", podcast_id=podcast_id, status="success"
            )
            db.add(txn)
            db.commit()
            return RedirectResponse("/success", status_code=302)

        return RedirectResponse("/checkout", status_code=302)

    @app.get("/success", response_class=HTMLResponse)
    def success(request: Request):
        return templates.TemplateResponse("front/success.html", {"request": request})

    return app


app = create_app()


# Helpers
def _get_or_create_user(request: Request, db: Session) -> models.User | None:
    tg_id = request.session.get("telegram_id")
    if not tg_id:
        return None

    user = db.query(models.User).filter(models.User.telegram_id == str(tg_id)).first()
    if not user:
        user = models.User(telegram_id=str(tg_id))
        db.add(user)
        db.commit()
        db.refresh(user)
        logging.getLogger(ACCESS_LOGGER_NAME).info(
            "created user for telegram_id=%s ip=%s", tg_id, getattr(request.client, "host", "-")
        )
    return user


def _user_has_full_access(user: models.User | None, podcast: models.Podcast, db: Session) -> bool:
    if not user:
        return False
    if user.has_subscription:
        return True
    # free podcast
    if podcast.is_free:
        return True
    # check single purchase
    has_single = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.user_id == user.id,
            models.Transaction.type == "single",
            models.Transaction.podcast_id == podcast.id,
            models.Transaction.status == "success",
        )
        .first()
        is not None
    )
    return bool(has_single)
