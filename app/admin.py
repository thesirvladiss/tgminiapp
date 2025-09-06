from typing import Optional
from datetime import datetime
import os

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import get_db
from . import models
from .auth import require_auth, is_authenticated
from .config import settings

try:
    from mutagen.mp3 import MP3
except Exception:  # pragma: no cover
    MP3 = None  # type: ignore

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/admin")


def _guard(request: Request) -> Optional[RedirectResponse]:
    return require_auth(request)


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    total_published = db.query(models.Podcast).filter(models.Podcast.is_published.is_(True)).count()
    total_transactions = db.query(models.Transaction).count()
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "stats": {
                "published": total_published,
                "transactions": total_transactions,
            },
        },
    )


# Projects CRUD
@router.get("/projects", response_class=HTMLResponse)
def projects_list(request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    items = db.query(models.ProjectCard).order_by(models.ProjectCard.order.asc()).all()
    return templates.TemplateResponse("admin/projects_list.html", {"request": request, "items": items})


@router.get("/projects/create", response_class=HTMLResponse)
def project_create_form(request: Request):
    if redirect := _guard(request):
        return redirect
    return templates.TemplateResponse("admin/project_form.html", {"request": request, "item": None})


@router.post("/projects/create")
def project_create(
    request: Request,
    title: str = Form(...),
    url: str = Form(...),
    order: int = Form(0),
    is_internal: bool = Form(False),
    db: Session = Depends(get_db),
):
    if redirect := _guard(request):
        return redirect
    item = models.ProjectCard(title=title, url=url, order=order, is_internal=is_internal)
    db.add(item)
    db.commit()
    return RedirectResponse(url="/admin/projects", status_code=302)


@router.get("/projects/{project_id}/edit", response_class=HTMLResponse)
def project_edit_form(project_id: int, request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    item = db.get(models.ProjectCard, project_id)
    if not item:
        return RedirectResponse("/admin/projects", status_code=302)
    return templates.TemplateResponse("admin/project_form.html", {"request": request, "item": item})


@router.post("/projects/{project_id}/edit")
def project_edit(
    project_id: int,
    request: Request,
    title: str = Form(...),
    url: str = Form(...),
    order: int = Form(0),
    is_internal: bool = Form(False),
    db: Session = Depends(get_db),
):
    if redirect := _guard(request):
        return redirect
    item = db.get(models.ProjectCard, project_id)
    if not item:
        return RedirectResponse("/admin/projects", status_code=302)
    item.title = title
    item.url = url
    item.order = order
    item.is_internal = is_internal
    db.commit()
    return RedirectResponse(url="/admin/projects", status_code=302)


@router.post("/projects/{project_id}/delete")
def project_delete(project_id: int, request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    item = db.get(models.ProjectCard, project_id)
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin/projects", status_code=302)


# Podcasts CRUD
@router.get("/podcasts", response_class=HTMLResponse)
def podcasts_list(request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    items = db.query(models.Podcast).order_by(models.Podcast.published_at.desc()).all()
    return templates.TemplateResponse("admin/podcasts_list.html", {"request": request, "items": items})


@router.get("/podcasts/create", response_class=HTMLResponse)
def podcast_create_form(request: Request):
    if redirect := _guard(request):
        return redirect
    return templates.TemplateResponse("admin/podcast_form.html", {"request": request, "item": None})


@router.post("/podcasts/create")
def podcast_create(
    request: Request,
    title: str = Form(...),
    description: str = Form("") ,
    category: str = Form("") ,
    published_at: str = Form("") ,
    is_published: bool = Form(False),
    cover: UploadFile | None = File(None),
    full: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if redirect := _guard(request):
        return redirect

    cover_path = _save_upload(cover) if cover else None
    full_path = _save_upload(full) if full else None
    duration = _get_duration_seconds(full_path) if full_path else 0

    pub_dt = datetime.fromisoformat(published_at) if published_at else datetime.utcnow()

    item = models.Podcast(
        title=title,
        description=description,
        category=category,
        published_at=pub_dt,
        duration_seconds=duration,
        cover_path=cover_path,
        audio_full_path=full_path,
        is_published=is_published,
    )
    db.add(item)
    db.commit()
    return RedirectResponse("/admin/podcasts", status_code=302)


@router.get("/podcasts/{podcast_id}/edit", response_class=HTMLResponse)
def podcast_edit_form(podcast_id: int, request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    item = db.get(models.Podcast, podcast_id)
    if not item:
        return RedirectResponse("/admin/podcasts", status_code=302)
    return templates.TemplateResponse("admin/podcast_form.html", {"request": request, "item": item})


@router.post("/podcasts/{podcast_id}/edit")
def podcast_edit(
    podcast_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form("") ,
    category: str = Form("") ,
    published_at: str = Form("") ,
    is_published: bool = Form(False),
    cover: UploadFile | None = File(None),
    full: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if redirect := _guard(request):
        return redirect
    item = db.get(models.Podcast, podcast_id)
    if not item:
        return RedirectResponse("/admin/podcasts", status_code=302)

    item.title = title
    item.description = description
    item.category = category
    item.published_at = datetime.fromisoformat(published_at) if published_at else item.published_at
    item.is_published = is_published
    if cover:
        item.cover_path = _save_upload(cover)
    if full:
        item.audio_full_path = _save_upload(full)
        item.duration_seconds = _get_duration_seconds(item.audio_full_path)

    db.commit()
    return RedirectResponse("/admin/podcasts", status_code=302)


@router.post("/podcasts/{podcast_id}/delete")
def podcast_delete(podcast_id: int, request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    item = db.get(models.Podcast, podcast_id)
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse("/admin/podcasts", status_code=302)


@router.get("/transactions", response_class=HTMLResponse)
def transactions(request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    items = db.query(models.Transaction).order_by(models.Transaction.created_at.desc()).all()
    return templates.TemplateResponse("admin/transactions_list.html", {"request": request, "items": items})


@router.get("/users", response_class=HTMLResponse)
def users(request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    items = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return templates.TemplateResponse("admin/users.html", {"request": request, "items": items})


@router.get("/users/{user_id}/edit", response_class=HTMLResponse)
def user_edit_form(user_id: int, request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    user = db.get(models.User, user_id)
    if not user:
        return RedirectResponse("/admin/users", status_code=302)
    return templates.TemplateResponse("admin/user_form.html", {"request": request, "item": user})


@router.post("/users/{user_id}/edit")
def user_edit(
    user_id: int,
    request: Request,
    telegram_id: str = Form(...),
    has_subscription: bool = Form(False),
    db: Session = Depends(get_db),
):
    if redirect := _guard(request):
        return redirect
    user = db.get(models.User, user_id)
    if not user:
        return RedirectResponse("/admin/users", status_code=302)
    user.telegram_id = telegram_id
    user.has_subscription = has_subscription
    db.commit()
    return RedirectResponse("/admin/users", status_code=302)


def _save_upload(file: UploadFile | None) -> Optional[str]:
    if not file:
        return None
    safe_name = f"{datetime.utcnow().timestamp()}_{file.filename.replace(' ', '_')}"
    dest_path = os.path.join(settings.uploads_dir, safe_name)
    with open(dest_path, "wb") as f:
        f.write(file.file.read())
    return f"/{settings.uploads_dir}/{safe_name}"


def _get_duration_seconds(path: Optional[str]) -> int:
    if not path or not MP3:
        return 0
    full_path = path.lstrip("/")
    try:
        audio = MP3(full_path)
        return int(audio.info.length)
    except Exception:
        return 0


