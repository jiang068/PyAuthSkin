# pyauthskin/web.py

import hashlib
import re
import uuid
import io
from typing import Optional
from pathlib import Path # Add missing import

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
    # Username validation
    if len(username) < 3 or len(username) > 20:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username must be between 3 and 20 characters"}, status_code=400)
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username can only contain letters, numbers, and underscores"}, status_code=400)
    
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
    
    # Fetch user skins and prefetch their associated texture (which contains width/height)
    user_skins = await UserTexture.filter(user=user).prefetch_related('texture')
    return templates.TemplateResponse("manager.html", {"request": request, "user": user, "skins": user_skins})


@router.post("/manager/upload")
async def upload_skin(
    request: Request,
    file: UploadFile = File(...),
    display_name: str = Form(...),
    model: str = Form("classic"),
    user: User = Depends(get_current_user)
):
    
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    # Display name validation
    if len(display_name) < 1 or len(display_name) > 50:
        return templates.TemplateResponse("manager.html", {"request": request, "user": user, "error": "Display name must be between 1 and 50 characters"}, status_code=400)

    # File size limit: 1MB
    contents = await file.read()
    if len(contents) > 1024 * 1024:
        return templates.TemplateResponse("manager.html", {"request": request, "user": user, "error": "File size must be less than 1MB"}, status_code=400)

    # File type validation
    if not file.content_type or not file.content_type.startswith("image/png"):
        return templates.TemplateResponse("manager.html", {"request": request, "user": user, "error": "Only PNG files are allowed"}, status_code=400)
    
    # Validate PNG content
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(contents))
        img.verify()  # Verify it's a valid image
        if img.format != "PNG":
            raise ValueError("Not PNG")
    except Exception:
        return templates.TemplateResponse("manager.html", {"request": request, "user": user, "error": "Invalid PNG file"}, status_code=400)

    file_hash = hashlib.sha256(contents).hexdigest()[:8]
    file_hash = hashlib.sha256(contents).hexdigest()[:8]
    
    # Use absolute paths from DATA_DIR for file operations
    skins_dir = DATA_DIR / "skins"
    skin_path = skins_dir / f"{file_hash}.png"
    avatar_path = skins_dir / f"{file_hash}_avatar.png"

    with open(skin_path, "wb") as f:
        f.write(contents)

    # Get image dimensions using Pillow within this function's scope
    from PIL import Image # Import Image here to avoid circular dependency if skins_render also imports main
    with Image.open(skin_path) as img:
        skin_width, skin_height = img.size

    texture = await Texture.filter(hash=file_hash).first()
    if not texture:
        texture = await Texture.create(
            hash=file_hash,
            path=str(skin_path),
            uploader=user,
            width=skin_width, # Store actual width
            height=skin_height # Store actual height
        )
    
    await UserTexture.filter(user=user, is_active_skin=True).update(is_active_skin=False)
    await UserTexture.create(user=user, texture=texture, display_name=display_name, model=model, is_active_skin=True)

    # Pass the actual skin dimensions to generate_avatar
    generate_avatar(skin_path, avatar_path, width=skin_width, height=skin_height)

    return RedirectResponse(url="/manager", status_code=303)

@router.post("/manager/set_active/{skin_id}")
async def set_active_skin(skin_id: int, request: Request, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    await UserTexture.filter(user=user, is_active_skin=True).update(is_active_skin=False)
    await UserTexture.filter(id=skin_id, user=user).update(is_active_skin=True)
    
    return RedirectResponse(url="/manager", status_code=303)

@router.post("/manager/delete_skin/{skin_id}")
async def delete_skin(skin_id: int, request: Request, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    # Find the UserTexture entry
    user_texture = await UserTexture.filter(user=user, id=skin_id).first()
    if not user_texture:
        raise HTTPException(status_code=404, detail="Skin not found or not owned by user")

    # Get the associated Texture object
    texture = await user_texture.texture

    # If this was the active skin, deactivate it (or set a default if available)
    if user_texture.is_active_skin:
        # For simplicity, we'll just deactivate it. User will have no active skin.
        # A more complex system might assign a default skin.
        pass # No change needed here, as deactivation is handled by setting a new active skin.

    # Delete the UserTexture entry
    await user_texture.delete()

    # Check if this texture is still used by any other UserTexture entry.
    # If not, delete the physical file to save space.
    # We need to explicitly check for other UserTexture entries that reference this specific Texture.
    other_user_textures_referencing_this_texture = await UserTexture.filter(texture=texture).exists()
    
    if not other_user_textures_referencing_this_texture:
        # No other UserTexture entries are using this Texture, so we can delete the physical file.
        skin_file_path = Path(texture.path)
        if skin_file_path.exists():
            skin_file_path.unlink()
            # Also delete the avatar if it exists
            avatar_file_path = skin_file_path.parent / f"{skin_file_path.stem}_avatar.png"
            if avatar_file_path.exists():
                avatar_file_path.unlink()
        await texture.delete() # Delete the Texture entry itself, as it's no longer referenced.

    return RedirectResponse(url="/manager", status_code=303)
