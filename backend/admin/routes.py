from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(ROOT / "admin_panel" / "templates"))

router = APIRouter(tags=["admin-ui"])


@router.get("/admin", response_class=HTMLResponse)
@router.get("/admin/", response_class=HTMLResponse)
async def admin_index(request: Request):
    token = request.cookies.get("admin_token")
    if not token:
        return RedirectResponse("/admin/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/admin/users", response_class=HTMLResponse)
async def users_page(request: Request):
    if not request.cookies.get("admin_token"):
        return RedirectResponse("/admin/login")
    return templates.TemplateResponse("users.html", {"request": request})


@router.get("/admin/tests", response_class=HTMLResponse)
async def tests_page(request: Request):
    if not request.cookies.get("admin_token"):
        return RedirectResponse("/admin/login")
    return templates.TemplateResponse("tests.html", {"request": request})


@router.get("/admin/payments", response_class=HTMLResponse)
async def payments_page(request: Request):
    if not request.cookies.get("admin_token"):
        return RedirectResponse("/admin/login")
    return templates.TemplateResponse("payments.html", {"request": request})


@router.get("/admin/processing", response_class=HTMLResponse)
async def processing_page(request: Request):
    if not request.cookies.get("admin_token"):
        return RedirectResponse("/admin/login")
    return templates.TemplateResponse("processing.html", {"request": request})


@router.get("/admin/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    if not request.cookies.get("admin_token"):
        return RedirectResponse("/admin/login")
    return templates.TemplateResponse("settings.html", {"request": request})


@router.get("/admin/logout")
async def logout():
    response = RedirectResponse("/admin/login")
    response.delete_cookie("admin_token")
    return response
