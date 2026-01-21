import base64
import time
import json
from fastapi import APIRouter, HTTPException, Body
from .database import User, Texture, UserTexture
from config import BASE_URL # Changed to absolute import
from .security import pwd_context
from typing import Dict, Any
from . import keystore
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from config import AUTH_API_PREFIX # Import the custom prefix

# Define the router with a common base prefix
router = APIRouter(prefix=AUTH_API_PREFIX, tags=["Yggdrasil"])

def sign_data(data: bytes) -> bytes:
    """Signs the given data with the server's private key."""
    if not keystore.SIGNING_PRIVATE_KEY:
        raise RuntimeError("Server private key not loaded.")
    
    return keystore.SIGNING_PRIVATE_KEY.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA1()
    )

async def get_user_profile_data(uuid: str):
    try:
        # Ensure the UUID format is consistent (no hyphens)
        clean_uuid = uuid.replace('-', '')
        user = await User.get(uuid=clean_uuid)
        
        # Find the user's active skin relation, prefetching the texture object
        active_skin_relation = await UserTexture.get_or_none(user=user, is_active_skin=True).prefetch_related('texture')
        
        textures_data = {}
        if active_skin_relation:
            active_skin = active_skin_relation.texture
            skin_model = active_skin_relation.model # This will be 'classic' or 'slim'
            
            skin_metadata = {}
            if skin_model == 'slim':
                skin_metadata['model'] = 'slim'

            textures_data["SKIN"] = {
                "url": f"{BASE_URL}/skins/{active_skin.hash}.png", # Update URL path
                "metadata": skin_metadata
            }

        # The value of the "textures" property must be a signed JSON string
        profile_textures = {
            "timestamp": int(time.time() * 1000),
            "profileId": user.uuid,
            "profileName": user.username,
            "textures": textures_data
        }
        
        # To ensure canonical representation, dump the JSON without any whitespace.
        textures_json = json.dumps(profile_textures, separators=(',', ':')).encode('utf-8')
        
        # Sign the JSON data
        signature = sign_data(textures_json)
        
        return {
            "id": user.uuid,
            "name": user.username,
            "properties": [{
                "name": "textures",
                "value": base64.b64encode(textures_json).decode('utf-8'),
                "signature": base64.b64encode(signature).decode('utf-8')
            }]
        }
    except Exception as e:
        print(f"Error getting user profile: {e}") # Added for debugging
        raise HTTPException(status_code=404, detail="User not found")

@router.post("/authserver/authenticate")
async def authenticate(data: Dict[str, Any] = Body(...)):
    login_username = data.get("username")
    password = data.get("password")

    if not login_username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    # Strip the @test.com suffix if it exists
    db_username = login_username
    if db_username.endswith("@test.com"):
        db_username = db_username[:-len("@test.com")]

    try:
        user = await User.get(username=db_username)
        if not pwd_context.verify(password, user.password):
            raise HTTPException(status_code=403, detail="Invalid credentials")
        
        # The response must include `availableProfiles` for launchers like PCL2.
        profile = {
            "id": user.uuid,
            "name": user.username
        }
        
        return {
            "accessToken": "fake-token-for-now",
            "clientToken": data.get("clientToken"),
            "availableProfiles": [profile], # Add the list of available profiles
            "selectedProfile": profile,
            "user": {
                "id": user.uuid,
                "properties": []
            }
        }
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid credentials")

# Correct the session server path
@router.get("/sessionserver/session/minecraft/profile/{uuid}")
async def get_profile(uuid: str):
    return await get_user_profile_data(uuid)