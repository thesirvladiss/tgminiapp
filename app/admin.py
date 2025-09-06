from typing import Optional
from datetime import datetime
import os

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import StreamingResponse
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


def _has_file(upload: UploadFile | None) -> bool:
    try:
        return bool(upload and getattr(upload, "filename", None))
    except Exception:
        return False


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    total_podcasts = db.query(models.Podcast).count()
    total_published = db.query(models.Podcast).filter(models.Podcast.is_published.is_(True)).count()
    total_drafts = max(0, total_podcasts - total_published)
    total_users = db.query(models.User).count()
    total_subscriptions = db.query(models.User).filter(models.User.has_subscription.is_(True)).count()
    total_transactions = db.query(models.Transaction).count()
    total_success_tx = db.query(models.Transaction).filter(models.Transaction.status == "success").count()

    latest_podcasts = (
        db.query(models.Podcast)
        .order_by(models.Podcast.published_at.desc())
        .limit(5)
        .all()
    )
    latest_transactions = (
        db.query(models.Transaction)
        .order_by(models.Transaction.created_at.desc())
        .limit(5)
        .all()
    )
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "stats": {
                "podcasts": total_podcasts,
                "published": total_published,
                "drafts": total_drafts,
                "users": total_users,
                "subscriptions": total_subscriptions,
                "transactions": total_transactions,
                "success_tx": total_success_tx,
            },
            "latest_podcasts": latest_podcasts,
            "latest_transactions": latest_transactions,
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
    # map id->price
    prices = {pp.podcast_id: pp.price_cents for pp in db.query(models.PodcastPrice).all()}
    return templates.TemplateResponse("admin/podcasts_list.html", {"request": request, "items": items, "prices": prices})


@router.get("/podcasts/create", response_class=HTMLResponse)
def podcast_create_form(request: Request):
    if redirect := _guard(request):
        return redirect
    # provide empty prices map
    return templates.TemplateResponse("admin/podcast_form.html", {"request": request, "item": None, "prices": {}})


@router.post("/podcasts/create")
def podcast_create(
    request: Request,
    title: str = Form(...),
    description: str = Form("") ,
    category: str = Form("") ,
    published_at: str = Form("") ,
    is_published: bool = Form(False),
    is_free: bool = Form(False),
    price_rub: int = Form(0),
    cover: UploadFile | None = File(None),
    full: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if redirect := _guard(request):
        return redirect

    cover_path = _save_upload(cover) if _has_file(cover) else None
    full_path = _save_upload(full) if _has_file(full) else None
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
        is_free=is_free,
    )
    db.add(item)
    db.commit()
    # set price if provided
    try:
        price_cents = int(max(0, price_rub)) * 100
    except Exception:
        price_cents = 0
    pp = models.PodcastPrice(podcast_id=item.id, price_cents=price_cents)
    db.add(pp)
    db.commit()
    return RedirectResponse("/admin/podcasts", status_code=302)


@router.get("/podcasts/{podcast_id}/edit", response_class=HTMLResponse)
def podcast_edit_form(podcast_id: int, request: Request, db: Session = Depends(get_db)):
    if redirect := _guard(request):
        return redirect
    item = db.get(models.Podcast, podcast_id)
    if not item:
        return RedirectResponse("/admin/podcasts", status_code=302)
    prices = {pp.podcast_id: pp.price_cents for pp in db.query(models.PodcastPrice).filter(models.PodcastPrice.podcast_id == item.id)}
    return templates.TemplateResponse("admin/podcast_form.html", {"request": request, "item": item, "prices": prices})


@router.post("/podcasts/{podcast_id}/edit")
def podcast_edit(
    podcast_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form("") ,
    category: str = Form("") ,
    published_at: str = Form("") ,
    is_published: bool = Form(False),
    is_free: bool = Form(False),
    price_rub: int = Form(0),
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
    item.is_free = is_free
    if _has_file(cover):
        item.cover_path = _save_upload(cover)
    if _has_file(full):
        item.audio_full_path = _save_upload(full)
        item.duration_seconds = _get_duration_seconds(item.audio_full_path)

    db.commit()
    # update price
    try:
        price_cents = int(max(0, price_rub)) * 100
    except Exception:
        price_cents = 0
    existing = db.query(models.PodcastPrice).filter(models.PodcastPrice.podcast_id == item.id).first()
    if existing:
        existing.price_cents = price_cents
    else:
        db.add(models.PodcastPrice(podcast_id=item.id, price_cents=price_cents))
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


@router.get("/export")
def export_excel(request: Request, db: Session = Depends(get_db)):
    """Экспорт данных в CSV (совместимо с Excel без дополнительных зависимостей)."""
    import io, csv

    output = io.StringIO()
    writer = csv.writer(output)

    # Podcasts
    writer.writerow(["Podcasts"])
    writer.writerow(["id", "title", "category", "published_at", "duration_min", "is_published", "is_free"])
    for p in db.query(models.Podcast).order_by(models.Podcast.id.asc()).all():
        writer.writerow([
            p.id,
            p.title,
            p.category or "",
            p.published_at.strftime('%Y-%m-%d %H:%M') if p.published_at else "",
            (p.duration_seconds or 0)//60,
            1 if p.is_published else 0,
            1 if getattr(p, 'is_free', False) else 0,
        ])
    writer.writerow([])

    # Users
    writer.writerow(["Users"])
    writer.writerow(["id", "telegram_id", "has_subscription", "created_at"])
    for u in db.query(models.User).order_by(models.User.id.asc()).all():
        writer.writerow([
            u.id,
            u.telegram_id,
            1 if u.has_subscription else 0,
            u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else "",
        ])
    writer.writerow([])

    # Transactions
    writer.writerow(["Transactions"])
    writer.writerow(["id", "user_id", "type", "podcast_id", "status", "created_at"])
    for t in db.query(models.Transaction).order_by(models.Transaction.id.asc()).all():
        writer.writerow([
            t.id,
            t.user_id,
            t.type,
            t.podcast_id or "",
            t.status,
            t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else "",
        ])

    mem = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    headers = {
        "Content-Disposition": "attachment; filename=export.csv",
        "Content-Type": "text/csv; charset=utf-8",
    }
    return StreamingResponse(mem, headers=headers, media_type="text/csv")


