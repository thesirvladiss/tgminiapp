from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from .database import Base, engine, get_db
from . import models
from .auth import router as auth_router
from .admin import router as admin_router
from .config import settings
from .public import router as public_router


def create_app() -> FastAPI:
    app = FastAPI(title="PL Mini App")

    # Mount static and uploads
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    templates = Jinja2Templates(directory="templates")

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Session middleware for admin auth
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    # Routers
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(public_router)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, db: Session = Depends(get_db)):
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
        podcast = db.get(models.Podcast, podcast_id)
        if not podcast:
            return RedirectResponse("/podcasts")

        user = _get_or_create_user(request, db)
        has_access = _user_has_full_access(user, podcast, db)

        # Auto-grant first free podcast if eligible and not preview mode
        if not preview and not has_access and podcast.is_free and user and user.free_podcast_id is None:
            user.free_podcast_id = podcast.id
            db.commit()
            has_access = True

        audio_src = (
            podcast.audio_full_path if has_access and podcast.audio_full_path else podcast.audio_preview_path
        )

        # If still no audio, fallback demo
        if not audio_src:
            audio_src = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

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
        podcast = db.get(models.Podcast, podcast_id)
        if not podcast:
            return RedirectResponse("/podcasts")
        return templates.TemplateResponse(
            "front/free-issue.html", {"request": request, "podcast": podcast}
        )

    @app.get("/checkout", response_class=HTMLResponse)
    def checkout(podcast_id: int | None = None, request: Request = None):
        return templates.TemplateResponse(
            "front/subscription.html", {"request": request, "podcast_id": podcast_id}
        )

    @app.post("/checkout")
    def do_checkout(
        request: Request,
        db: Session = Depends(get_db),
        tariff: str = Form(...),  # 'subscription' or 'single'
        podcast_id: int | None = Form(None),
    ):
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
    # Try session
    tg_id = request.session.get("telegram_id")
    # Fallbacks for local testing
    if not tg_id:
        tg_id = request.query_params.get("tid") or request.headers.get("X-Telegram-User-Id")
        if tg_id:
            request.session["telegram_id"] = tg_id
    if not tg_id:
        # anonymous user - create a temporary one by IP for demo (optional)
        tg_id = f"guest:{request.client.host}"
        request.session["telegram_id"] = tg_id

    user = db.query(models.User).filter(models.User.telegram_id == str(tg_id)).first()
    if not user:
        user = models.User(telegram_id=str(tg_id))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _user_has_full_access(user: models.User | None, podcast: models.Podcast, db: Session) -> bool:
    if not user:
        return False
    if user.has_subscription:
        return True
    # free podcast if not used or same as used
    if podcast.is_free and (user.free_podcast_id is None or user.free_podcast_id == podcast.id):
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


