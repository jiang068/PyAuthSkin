import os
import hashlib
import uuid
from pathlib import Path # 导入 Path
from fastapi import FastAPI, Request, File, UploadFile, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tortoise.contrib.fastapi import register_tortoise
from tortoise.exceptions import DoesNotExist, IntegrityError
from models import User, Texture, UserTexture
from auth_logic import router as auth_router
from skins_render import generate_avatar
from config import BASE_URL, HOST, PORT
from security import pwd_context
from typing import Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import base64
from contextlib import asynccontextmanager
import keystore # Import the keystore

# --- Security Setup ---
# pwd_context is now in security.py

# --- Lifespan manager for startup events ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load keys on startup
    generate_and_load_keys()
    yield
    # Shutdown logic can go here if needed

app = FastAPI(lifespan=lifespan)

# --- Base Directory for absolute paths ---
BASE_DIR = Path(__file__).resolve().parent

# --- RSA Key Generation and Loading ---
PUBLIC_KEY_PATH = BASE_DIR / "public.pem"
PRIVATE_KEY_PATH = BASE_DIR / "private.key"

def generate_and_load_keys():
    private_key_obj = None
    if not PUBLIC_KEY_PATH.exists() or not PRIVATE_KEY_PATH.exists():
        print("Generating new RSA key pair...")
        private_key_obj = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key_obj = private_key_obj.public_key()

        with open(PRIVATE_KEY_PATH, "wb") as f:
            f.write(private_key_obj.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        with open(PUBLIC_KEY_PATH, "wb") as f:
            f.write(public_key_obj.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))
    
    # Load the private key from file
    with open(PRIVATE_KEY_PATH, "rb") as f:
        keystore.SIGNING_PRIVATE_KEY = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )

    # According to the authlib-injector source code, the public key
    # must be the full, raw PEM content including headers and newlines.
    with open(PUBLIC_KEY_PATH, "r") as f:
        keystore.SIGNATURE_PUBLIC_KEY_B64 = f.read()


# The old @app.on_event is now replaced by the lifespan manager
# @app.on_event("startup")
# async def startup_event():
#     generate_and_load_keys()


# --- Mount static files & Setup templates ---
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# --- Include the auth router for the game client ---
app.include_router(auth_router)


# --- Dependency for getting current user from session cookie ---
async def get_current_user(request: Request) -> Optional[User]:
    user_id = request.session.get("user_id")
    if user_id:
        try:
            return await User.get(id=user_id)
        except DoesNotExist:
            return None
    return None

# --- Metadata Endpoints ---
@app.get("/")
@app.get("/api/yggdrasil") # Add endpoint for authlib-injector
async def root():
    return {
        "meta": {
            "serverName": "My Python Skin Server",
            "implementationName": "BlessingPython",
            "implementationVersion": "0.1.0"
        },
        "skinDomains": [HOST], # Only provide the hostname
        "signaturePublickey": keystore.SIGNATURE_PUBLIC_KEY_B64 # Use the key from keystore
    }

# --- Web UI Endpoints ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_form(request: Request, response: Response, username: str = Form(...), password: str = Form(...)):
    try:
        user = await User.get(username=username)
        # No pre-hashing needed for argon2
        if not pwd_context.verify(password, user.password):
            raise DoesNotExist
        request.session["user_id"] = user.id
        return RedirectResponse(url="/manager", status_code=303)
    except DoesNotExist:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"}, status_code=400)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...)):
    # No pre-hashing needed for argon2
    hashed_password = pwd_context.hash(password)
    try:
        # Store UUID without hyphens to match game client requests
        user_uuid = str(uuid.uuid4()).replace('-', '')
        user = await User.create(username=username, password=hashed_password, uuid=user_uuid)
        
        # Automatically log in after registration
        request.session["user_id"] = user.id
        return RedirectResponse(url="/manager", status_code=303)
    except IntegrityError:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"}, status_code=400)


@app.get("/manager", response_class=HTMLResponse)
async def manager(request: Request, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    
    user_skins = await UserTexture.filter(user=user).prefetch_related('texture')
    return templates.TemplateResponse("manager.html", {"request": request, "user": user, "skins": user_skins})


@app.post("/manager/upload")
async def upload_skin(file: UploadFile = File(...), display_name: str = Form(...), user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    contents = await file.read()
    # Truncate the SHA256 hash to the first 8 characters
    file_hash = hashlib.sha256(contents).hexdigest()[:8]
    
    # Use absolute paths for file operations
    skins_dir = BASE_DIR / "static" / "skins"
    skins_dir.mkdir(exist_ok=True) # Ensure the directory exists
    skin_path = skins_dir / f"{file_hash}.png"
    avatar_path = skins_dir / f"{file_hash}_avatar.png"

    with open(skin_path, "wb") as f:
        f.write(contents)

    texture, _ = await Texture.get_or_create(hash=file_hash, defaults={"path": str(skin_path), "uploader": user})
    
    await UserTexture.filter(user=user, is_active_skin=True).update(is_active_skin=False)
    await UserTexture.create(user=user, texture=texture, display_name=display_name, is_active_skin=True)

    generate_avatar(skin_path, avatar_path)

    return RedirectResponse(url="/manager", status_code=303)

@app.post("/manager/set_active/{skin_id}")
async def set_active_skin(skin_id: int, user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=403)

    # Deactivate all other skins for the user
    await UserTexture.filter(user=user, is_active_skin=True).update(is_active_skin=False)
    
    # Activate the selected skin
    await UserTexture.filter(id=skin_id, user=user).update(is_active_skin=True)
    
    return RedirectResponse(url="/manager", status_code=303)


# --- Database Registration ---
register_tortoise(
    app,
    db_url="sqlite://database.db",
    modules={"models": ["models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

# --- Middleware for Session ---
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key="your-super-secret-key")


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run(app, host=HOST, port=PORT)
