from typing import Optional
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import settings

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/admin")


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("admin_authenticated"))


def require_auth(request: Request) -> Optional[RedirectResponse]:
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return None


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == settings.admin_login and password == settings.admin_password:
        request.session["admin_authenticated"] = True
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse(
        "admin/login.html", {"request": request, "error": "Неверный логин или пароль"}
    )


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)

