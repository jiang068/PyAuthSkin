# pyauthskin/web.py

import hashlib
import re
import uuid
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, Request,
                     Response, UploadFile)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from tortoise.exceptions import DoesNotExist, IntegrityError

from config import BASE_DIR, DATA_DIR
from .database import User, Texture, UserTexture
from .security import pwd_context
from .skins_render import generate_avatar

# Create a new router for the web interface
router = APIRouter()

# Templates are needed for the web routes
templates = Jinja2Templates(directory=BASE_DIR / "site")

# --- Dependency for getting current user from session cookie ---
async def get_current_user(request: Request) -> Optional[User]:
    user_id = request.session.get("user_id")
    if user_id:
        try:
            return await User.get(id=user_id)
        except DoesNotExist:
            return None
    return None

# --- Web UI Endpoints ---

@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/manager")
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login_form(request: Request, response: Response, username: str = Form(...), password: str = Form(...)):
    try:
        user = await User.get(username=username)
        if not pwd_context.verify(password, user.password):
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"}, status_code=400)
        
        request.session["user_id"] = user.id
        return RedirectResponse(url="/manager", status_code=303)
    except DoesNotExist:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"}, status_code=400)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: User = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/manager")
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...)):
    # Password policy validation
    if len(password) < 8:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Password must be at least 8 characters long"}, status_code=400)
    if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password):
        return templates.TemplateResponse("register.html", {"request": request, "error": "Password must contain both uppercase and lowercase letters"}, status_code=400)

    hashed_password = pwd_context.hash(password)
    try:
        user_uuid = str(uuid.uuid4()).replace('-', '')
        user = await User.create(username=username, password=hashed_password, uuid=user_uuid)
        
        request.session["user_id"] = user.id
        return RedirectResponse(url="/manager", status_code=303)
    except IntegrityError:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"}, status_code=400)

@router.get("/manager", response_class=HTMLResponse)
async def manager(request: Request, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    
    user_skins = await UserTexture.filter(user=user).prefetch_related('texture')
    return templates.TemplateResponse("manager.html", {"request": request, "user": user, "skins": user_skins})

@router.post("/manager/upload")
async def upload_skin(file: UploadFile = File(...), display_name: str = Form(...), model: str = Form("classic"), user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()[:8]
    
    skins_dir = DATA_DIR / "static" / "skins"
    skin_path = skins_dir / f"{file_hash}.png"
    avatar_path = skins_dir / f"{file_hash}_avatar.png"

    with open(skin_path, "wb") as f:
        f.write(contents)

    texture = await Texture.filter(hash=file_hash).first()
    if not texture:
        texture = await Texture.create(
            hash=file_hash,
            path=str(skin_path),
            uploader=user
        )
    
    await UserTexture.filter(user=user, is_active_skin=True).update(is_active_skin=False)
    await UserTexture.create(user=user, texture=texture, display_name=display_name, model=model, is_active_skin=True)

    generate_avatar(skin_path, avatar_path)

    return RedirectResponse(url="/manager", status_code=303)

@router.post("/manager/set_active/{skin_id}")
async def set_active_skin(skin_id: int, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    await UserTexture.filter(user=user, is_active_skin=True).update(is_active_skin=False)
    await UserTexture.filter(id=skin_id, user=user).update(is_active_skin=True)
    
    return RedirectResponse(url="/manager", status_code=303)
