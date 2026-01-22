import base64
from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
import os
import secrets

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request, File, UploadFile, Form, Depends, HTTPException, Response # Add Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tortoise.contrib.fastapi import register_tortoise
from tortoise.exceptions import DoesNotExist, IntegrityError
from contextlib import asynccontextmanager
from typing import Optional
import re # Import regular expressions for password validation

# --- Cryptography imports for key generation ---
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import base64

# --- Import from our new package ---
from pyauthskin.database import User, Player, Texture
from pyauthskin.auth_logic import router as auth_router
from pyauthskin.skins_render import generate_avatar
from pyauthskin.security import pwd_context
from pyauthskin import keystore
from pyauthskin.web import router as web_router # Import the new web router

# --- Config and Paths ---
from config import BASE_DIR, DATA_DIR, HOST, PORT, AUTH_API_PREFIX, CORS_ALLOWED_ORIGINS, CORS_ALLOW_CREDENTIALS, CORS_ALLOWED_METHODS, CORS_ALLOWED_HEADERS

# --- Pre-startup Directory Creation ---
# Ensure all necessary data directories exist before the app is created.
# This prevents errors when mounting static files.
(DATA_DIR / "skins").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "site").mkdir(parents=True, exist_ok=True) # Ensure site directory exists

# --- Lifespan manager for startup events ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Tortoise ORM
    from tortoise.contrib.fastapi import register_tortoise
    register_tortoise(
        app,
        db_url=f"sqlite://{DATA_DIR / 'database.db'}",
        modules={"models": ["pyauthskin.database"]},
        generate_schemas=True,
        add_exception_handlers=True,
    )
    generate_and_load_keys()
    yield

app = FastAPI(lifespan=lifespan)

# --- RSA Key Generation and Loading ---
PUBLIC_KEY_PATH = DATA_DIR / "public.pem"
PRIVATE_KEY_PATH = DATA_DIR / "private.key"

def generate_and_load_keys():
    # print("Starting key generation/loading...") # debug
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
    
    # print("Loading existing keys...") # debug
    with open(PRIVATE_KEY_PATH, "rb") as f:
        keystore.SIGNING_PRIVATE_KEY = serialization.load_pem_private_key(
            f.read(), password=None, backend=default_backend()
        )
        # print(f"Private key loaded successfully: {keystore.SIGNING_PRIVATE_KEY is not None}") # debug
    with open(PUBLIC_KEY_PATH, "rb") as f:
        public_key_pem = f.read()
        public_key_obj = serialization.load_pem_public_key(public_key_pem, backend=default_backend())
        # Export public key as PEM (SubjectPublicKeyInfo). authlib-injector expects
        # a PEM block for signaturePublickey (KeyUtils.decodePEMPublicKey will
        # remove newlines and parse the inner base64).
        public_key_pem = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        keystore.SIGNATURE_PUBLIC_KEY_B64 = public_key_pem.decode('utf-8')
        # print(f"Public key loaded successfully (PEM), length: {len(keystore.SIGNATURE_PUBLIC_KEY_B64)}")  # debug

# --- Mount static files ---
app.mount("/skins", StaticFiles(directory=DATA_DIR / "skins"), name="skins")

# --- Initialize Templates and attach to app state ---
templates = Jinja2Templates(directory=BASE_DIR / "site")
app.state.templates = templates # Attach templates to app state

# --- Include Routers ---
app.include_router(auth_router) # For the game client
app.include_router(web_router)  # For the web interface

# --- Mount site static files after routers ---
app.mount("/", StaticFiles(directory=BASE_DIR / "site"), name="site")

# --- Database Registration ---
register_tortoise(
    app,
    db_url=f"sqlite://{DATA_DIR / 'database.db'}",
    modules={"models": ["pyauthskin.database"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

# --- Middleware for Session ---
from starlette.middleware.sessions import SessionMiddleware # Add SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException # Import Starlette's HTTPException
from starlette.requests import Request as StarletteRequest # Explicitly import Request for the handler
from starlette.middleware.cors import CORSMiddleware

# --- CSRF Protection ---
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError

# --- Rate Limiting ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Get session secret from env or generate random
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOWED_METHODS,
    allow_headers=CORS_ALLOWED_HEADERS,
)

# --- Custom 404 Error Handler ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: StarletteRequest, exc: StarletteHTTPException):
    if exc.status_code == 404:
        # Access templates from app state
        return request.app.state.templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    elif exc.status_code == 204:
        # Handle 204 No Content properly
        return Response(status_code=204)
    elif exc.status_code == 403:
        # Handle 403 Forbidden properly
        return JSONResponse(status_code=403, content={"error": "Forbidden", "errorMessage": exc.detail})
    elif exc.status_code == 405:
        # Handle 405 Method Not Allowed
        return JSONResponse(status_code=405, content={"error": "Method Not Allowed", "errorMessage": exc.detail})
    # For other HTTP exceptions, re-raise to let default handler take over
    raise exc

# --- Custom FastAPI HTTP Exception Handler ---
@app.exception_handler(HTTPException)
async def fastapi_http_exception_handler(request: StarletteRequest, exc: HTTPException):
    if exc.status_code == 403:
        # Handle 403 Forbidden properly for FastAPI HTTPException
        return JSONResponse(status_code=403, content={"error": "Forbidden", "errorMessage": exc.detail})
    elif exc.status_code == 405:
        # Handle 405 Method Not Allowed
        return JSONResponse(status_code=405, content={"error": "Method Not Allowed", "errorMessage": exc.detail})
    # For other HTTP exceptions, re-raise to let default handler take over
    raise exc


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT, LOG_LEVEL # Import LOG_LEVEL
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True, log_level=LOG_LEVEL) # Set log_level

# --- Web UI Endpoints (moved to pyauthskin/web.py) ---
@app.get("/manager")
async def manager(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    user = await User.get(id=user["id"])
    textures = await UserTexture.filter(user=user)
    return request.app.state.templates.TemplateResponse("manager.html", {"request": request, "user": user, "textures": textures})

@app.post("/manager/upload")
async def upload_skin(request: Request, file: UploadFile = File(...), display_name: str = Form(...), model: str = Form(...)):
    user = request.session.get("user")
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    user = await User.get(id=user["id"])
    file_location = DATA_DIR / "skins" / file.filename

    # Save the uploaded file to the designated location
    with open(file_location, "wb") as f:
        content = await file.read()
        f.write(content)

    # Create or update the texture record in the database
    texture, created = await Texture.get_or_create(
        name=display_name,
        defaults={"file_path": str(file_location)}
    )
    if not created:
        # If the texture already exists, update the file path
        texture.file_path = str(file_location)
        await texture.save()

    # Deactivate other skins for the user
    await UserTexture.filter(user=user, is_active_skin=True).update(is_active_skin=False)
    await UserTexture.create(user=user, texture=texture, display_name=display_name, model=model, is_active_skin=True)

    # Pass the actual skin dimensions to generate_avatar
    generate_avatar(skin_path, avatar_path, width=skin_width, height=skin_height)

    return RedirectResponse(url="/manager", status_code=303)
