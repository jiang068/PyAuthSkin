import base64
from contextlib import asynccontextmanager
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from tortoise.contrib.fastapi import register_tortoise

# --- Import from our new package ---
from pyauthskin import keystore
from pyauthskin.auth_logic import router as auth_router
from pyauthskin.web import router as web_router # Import the new web router

# --- Config and Paths ---
from config import BASE_DIR, DATA_DIR, HOST, PORT

# --- Pre-startup Directory Creation ---
# Ensure all necessary data directories exist before the app is created.
# This prevents errors when mounting static files.
(DATA_DIR / "skins").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "site").mkdir(parents=True, exist_ok=True) # Ensure site directory exists

# --- Lifespan manager for startup events ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    generate_and_load_keys()
    yield

app = FastAPI(lifespan=lifespan)

# --- RSA Key Generation and Loading ---
PUBLIC_KEY_PATH = DATA_DIR / "public.pem"
PRIVATE_KEY_PATH = DATA_DIR / "private.key"

def generate_and_load_keys():
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
    
    with open(PRIVATE_KEY_PATH, "rb") as f:
        keystore.SIGNING_PRIVATE_KEY = serialization.load_pem_private_key(
            f.read(), password=None, backend=default_backend()
        )
    with open(PUBLIC_KEY_PATH, "r") as f:
        keystore.SIGNATURE_PUBLIC_KEY_B64 = f.read()

# --- Mount static files ---
app.mount("/skins", StaticFiles(directory=DATA_DIR / "skins"), name="skins")

# --- Include Routers ---
app.include_router(auth_router) # For the game client
app.include_router(web_router)  # For the web interface

# --- Yggdrasil Metadata Endpoint ---
@app.get("/api/yggdrasil")
async def yggdrasil_meta():
    return {
        "meta": {
            "serverName": "PyAuthSkin",
            "implementationName": "PyAuthSkin",
            "implementationVersion": "1.0.0"
        },
        "skinDomains": [HOST],
        "signaturePublickey": keystore.SIGNATURE_PUBLIC_KEY_B64
    }

# --- Database Registration ---
register_tortoise(
    app,
    db_url=f"sqlite://{DATA_DIR / 'database.db'}",
    modules={"models": ["pyauthskin.database"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

# --- Middleware for Session ---
app.add_middleware(SessionMiddleware, secret_key="your-super-secret-key")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
