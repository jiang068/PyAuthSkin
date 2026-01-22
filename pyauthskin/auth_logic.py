import base64
import time
import json
from fastapi import APIRouter, HTTPException, Body
from .database import User, Player, Texture
from config import BASE_URL # Changed to absolute import
from .security import pwd_context
from typing import Dict, Any
from . import keystore
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from config import HOST, AUTH_API_PREFIX

# Define the router with a common base prefix
router = APIRouter(prefix=AUTH_API_PREFIX, tags=["Yggdrasil"])

# --- Yggdrasil Metadata Endpoint ---
# This must match the AUTH_API_PREFIX exactly, without a trailing slash.
@router.get("")
async def yggdrasil_meta():
    """Yggdrasil metadata endpoint."""
    return {
        "meta": {
            "serverName": "PyAuthSkin",
            "implementationName": "PyAuthSkin",
            "implementationVersion": "1.0.0"
        },
        "skinDomains": [HOST],
        "signaturePublickey": keystore.SIGNATURE_PUBLIC_KEY_B64
    }

def sign_data(data: bytes) -> bytes:
    """Signs the given data with the server's private key."""
    if not keystore.SIGNING_PRIVATE_KEY:
        raise RuntimeError("Server private key not loaded.")
    
    return keystore.SIGNING_PRIVATE_KEY.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA1()
    )

async def get_player_profile_data(uuid: str):
    try:
        # Ensure the UUID format is consistent (no hyphens)
        clean_uuid = uuid.replace('-', '')
        player = await Player.get(uuid=clean_uuid).prefetch_related('skin_texture')
        
        textures_data = {}
        if player.skin_texture:
            skin_model = player.skin_texture.model
            skin_metadata = {}
            if skin_model == 'slim':
                skin_metadata['model'] = 'slim'

            textures_data["SKIN"] = {
                "url": f"{BASE_URL}/skins/{player.skin_texture.hash}.png",
                "metadata": skin_metadata
            }

        # The value of the "textures" property must be a signed JSON string
        profile_textures = {
            "timestamp": int(time.time() * 1000),
            "profileId": player.uuid.replace('-', ''),  # Use unsigned UUID
            "profileName": player.name,
            "textures": textures_data
        }
        
        # To ensure canonical representation, dump the JSON without any whitespace.
        textures_json = json.dumps(profile_textures, separators=(',', ':')).encode('utf-8')
        
        # Sign the JSON data
        signature = sign_data(textures_json)
        
        return {
            "id": player.uuid.replace('-', ''),  # Use unsigned UUID
            "name": player.name,
            "properties": [{
                "name": "textures",
                "value": base64.b64encode(textures_json).decode('utf-8'),
                "signature": base64.b64encode(signature).decode('utf-8')
            }]
        }
    except Exception as e:
        print(f"Error getting player profile: {e}") # Added for debugging
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
        
        # Get all players for the user
        players = await Player.filter(user=user)
        # Format UUIDs without hyphens for Minecraft client (authlib-injector expects unsigned UUIDs)
        available_profiles = [{"id": p.uuid.replace('-', ''), "name": p.name} for p in players]
        
        # Select the first profile as selectedProfile
        selected_profile = available_profiles[0] if available_profiles else None
        
        return {
            "accessToken": "fake-token-for-now",
            "clientToken": data.get("clientToken"),
            "availableProfiles": available_profiles,
            "selectedProfile": selected_profile,
            "user": {
                "id": user.id,  # User id, not uuid
                "properties": []
            }
        }
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid credentials")

# Correct the session server path
@router.get("/sessionserver/session/minecraft/profile/{uuid}")
async def get_profile(uuid: str):
    return await get_player_profile_data(uuid)

@router.post("/authserver/refresh")
async def refresh(data: Dict[str, Any] = Body(...)):
    # Get the selected profile from the request
    selected_profile_data = data.get("selectedProfile")
    access_token = data.get("accessToken")
    
    if not access_token:
        raise HTTPException(status_code=400, detail="accessToken is required")
    
    # For now, we assume the user is authenticated via access token
    # In a real implementation, you'd validate the access token
    # For simplicity, we'll just return the selected profile if provided
    
    response = {
        "accessToken": "refreshed-fake-token",
        "clientToken": data.get("clientToken")
    }
    
    if selected_profile_data:
        # Validate that the selected profile exists and belongs to the user
        profile_uuid = selected_profile_data.get("id")
        profile_name = selected_profile_data.get("name")
        
        try:
            # Remove hyphens from UUID if present, then search in database
            clean_uuid = profile_uuid.replace('-', '')
            # For now, just check if the profile exists
            player = await Player.get(uuid=clean_uuid)
            # Return UUID without hyphens for consistency with authlib-injector
            response["selectedProfile"] = {
                "id": player.uuid.replace('-', ''),
                "name": player.name
            }
        except Exception as e:
            print(f"Error validating profile {profile_name} with UUID {profile_uuid}: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid profile: {profile_name}")
    
    return response