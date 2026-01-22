# pyauthskin/web.py

import hashlib
import re
import uuid
import io
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, Request,
                     Response, UploadFile, HTTPException)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from tortoise.exceptions import DoesNotExist, IntegrityError

from config import BASE_DIR, DATA_DIR
from .database import User, Player, Texture
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
        user = await User.create(username=username, password=hashed_password)
        player_uuid = str(uuid.uuid4()).replace('-', '')
        player = await Player.create(user=user, name=username, uuid=player_uuid)
        
        request.session["user_id"] = user.id
        return RedirectResponse(url="/manager", status_code=303)
    except IntegrityError:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"}, status_code=400)

@router.get("/manager", response_class=HTMLResponse)
async def manager(request: Request, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    
    # Fetch user skins and players
    skins = await Texture.filter(uploader=user)
    players = await Player.filter(user=user).prefetch_related('skin_texture')
    return templates.TemplateResponse("manager.html", {"request": request, "user": user, "skins": skins, "players": players})


@router.post("/manager/upload_skin")
async def upload_skin(
    request: Request,
    skin_file: UploadFile = File(...),
    display_name: str = Form(...),
    model: str = Form("classic"),  # Add model parameter
    user: User = Depends(get_current_user)
):
    
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    # Display name validation
    if len(display_name) < 1 or len(display_name) > 50:
        return templates.TemplateResponse("manager.html", {"request": request, "user": user, "error": "Display name must be between 1 and 50 characters"}, status_code=400)

    # File size limit: 1MB
    contents = await skin_file.read()
    if len(contents) > 1024 * 1024:
        return templates.TemplateResponse("manager.html", {"request": request, "user": user, "error": "File size must be less than 1MB"}, status_code=400)

    # File type validation
    if not skin_file.content_type or not skin_file.content_type.startswith("image/png"):
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
            width=skin_width,
            height=skin_height,
            display_name=display_name,
            model=model  # Save the model
        )
    
    # Pass the actual skin dimensions to generate_avatar
    generate_avatar(skin_path, avatar_path, width=skin_width, height=skin_height)

    return RedirectResponse(url="/manager", status_code=303)

@router.post("/manager/set_skin_for_player/{player_id}")
async def set_skin_for_player(player_id: int, request: Request, skin_id: Optional[str] = Form(None), user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    player = await Player.filter(id=player_id, user=user).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if skin_id is None or skin_id == "":
        player.skin_texture = None
    else:
        texture = await Texture.filter(id=int(skin_id), uploader=user).first()
        if not texture:
            raise HTTPException(status_code=404, detail="Skin not found")
        player.skin_texture = texture

    await player.save()
    return RedirectResponse(url="/manager", status_code=303)

    return RedirectResponse(url="/manager", status_code=303)

@router.post("/manager/delete_skin/{texture_id}")
async def delete_skin(texture_id: int, request: Request, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    texture = await Texture.filter(id=texture_id, uploader=user).first()
    if not texture:
        return Response(status_code=404)

    # Unset this skin from any players using it by updating the foreign key ID to null
    await Player.filter(skin_texture_id=texture.id).update(skin_texture_id=None)

    # Delete the skin file
    skin_path = DATA_DIR / "skins" / f"{texture.hash}.png"
    avatar_path = DATA_DIR / "skins" / f"{texture.hash}_avatar.png"

    # Delete the physical file
    if skin_path.exists():
        skin_path.unlink()
        # Also delete the avatar if it exists
        if avatar_path.exists():
            avatar_path.unlink()

    await texture.delete()
    return RedirectResponse(url="/manager", status_code=303)

@router.post("/manager/create_player")
async def create_player(request: Request, name: str = Form(...), user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    # Validate name
    if len(name) < 1 or len(name) > 255:
        raise HTTPException(status_code=400, detail="Player name must be between 1 and 255 characters")

    # Check if player name already exists for this user
    existing_player = await Player.filter(user=user, name=name).first()
    if existing_player:
        raise HTTPException(status_code=400, detail="Player name already exists")

    # Generate UUID for the player
    import uuid
    player_uuid = str(uuid.uuid4()).replace('-', '')

    # Create the player
    await Player.create(user=user, name=name, uuid=player_uuid)
    return RedirectResponse(url="/manager", status_code=303)

@router.post("/manager/delete_player/{player_id}")
async def delete_player(player_id: int, request: Request, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    player = await Player.filter(id=player_id, user=user).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    await player.delete()
    return RedirectResponse(url="/manager", status_code=303)
