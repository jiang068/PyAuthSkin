import base64
import time
import json
from fastapi import APIRouter, HTTPException, Body, Query, Response
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
        # Include common local loopback domains to avoid client-side rejection
        # when using localhost vs 127.0.0.1 as the skin host.
        "skinDomains": list({HOST, "127.0.0.1", "localhost"}),
        "signaturePublickey": keystore.SIGNATURE_PUBLIC_KEY_B64
    }

def sign_data(data: bytes) -> bytes:
    """Signs the given data with the server's private key."""
    # print(f"Debug: SIGNING_PRIVATE_KEY is None: {keystore.SIGNING_PRIVATE_KEY is None}")
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
        # Normalize stored UUID (which may be stored without hyphens) into
        # hyphenated form for the signed JSON's profileId.
        u = player.uuid
        if len(u) == 32 and '-' not in u:
            hyphen_uuid = f"{u[0:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:32]}"
        else:
            hyphen_uuid = u

        profile_textures = {
            "timestamp": int(time.time() * 1000),
            # Use hyphenated UUID in the signed textures JSON to match client
            # expectations.
            "profileId": hyphen_uuid,
            "profileName": player.name,
            "textures": textures_data
        }

        # To ensure canonical representation, dump the JSON without any whitespace
        # and preserve non-ASCII characters (avoid \uXXXX escapes).
        textures_json = json.dumps(profile_textures, separators=(',', ':'), ensure_ascii=False).encode('utf-8')

        # The Yggdrasil property 'value' is the base64 of the JSON. Some
        # verification paths operate on the raw JSON bytes while others may
        # verify against the base64-encoded string bytes. To maximize
        # compatibility, sign the base64-encoded value bytes (this matches the
        # behavior of several reference implementations).
        value_b64 = base64.b64encode(textures_json).decode('utf-8')
        signature = sign_data(value_b64.encode('utf-8'))

        return {
            "id": player.uuid.replace('-', ''),  # Use unsigned UUID
            "name": player.name,
            "properties": [{
                "name": "textures",
                "value": value_b64,
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

@router.get("/sessionserver/session/minecraft/hasJoined")
async def has_joined(username: str = Query(...), serverId: str = Query(...), ip: str = Query(None)):
    """Check if a player has joined the server."""
    try:
        # Find player by username
        player = await Player.get(name=username).prefetch_related('skin_texture')
        
        # For now, we don't validate serverId since we don't implement join
        # In a full implementation, you'd check if the player joined with this serverId
        
        # Return the profile data
        return await get_player_profile_data(player.uuid)
    except Exception as e:
        print(f"hasJoined error for {username}: {e}")
        # If player not found or any error, return 204 No Content
        raise HTTPException(status_code=204)

@router.head("/sessionserver/session/minecraft/hasJoined")
async def has_joined_head(username: str = Query(...), serverId: str = Query(...), ip: str = Query(None)):
    """HEAD version of hasJoined."""
    try:
        # Find player by username
        player = await Player.get(name=username).prefetch_related('skin_texture')
        
        # Return 200 OK with no body
        return Response(status_code=200)
    except Exception as e:
        print(f"hasJoined HEAD error for {username}: {e}")
        # If player not found or any error, return 204 No Content
        raise HTTPException(status_code=204)

@router.post("/sessionserver/session/minecraft/join")
async def join_server(data: Dict[str, Any] = Body(...)):
    """Record that a player has joined a server."""
    access_token = data.get("accessToken")
    selected_profile = data.get("selectedProfile")
    
    if not access_token:
        raise HTTPException(status_code=400, detail="accessToken is required")
    
    if not selected_profile:
        raise HTTPException(status_code=400, detail="selectedProfile is required")
    
    # For now, we don't validate the access token thoroughly
    # In a real implementation, you'd validate the token and check permissions
    if access_token != "fake-token-for-now" and access_token != "refreshed-fake-token":
        raise HTTPException(status_code=403, detail="Invalid access token")
    
    # Handle different formats of selectedProfile
    if isinstance(selected_profile, str):
        # selectedProfile is just the UUID string
        profile_uuid = selected_profile
        profile_name = None  # We don't have the name in this format
    elif isinstance(selected_profile, dict):
        # selectedProfile is an object with id and name
        profile_uuid = selected_profile.get("id")
        profile_name = selected_profile.get("name")
    else:
        raise HTTPException(status_code=400, detail="Invalid selectedProfile format")
    
    try:
        # Remove hyphens from UUID if present
        clean_uuid = profile_uuid.replace('-', '')
        player = await Player.get(uuid=clean_uuid)
        
        # In a full implementation, you'd store this join session
        # For now, just validate that the player exists
        print(f"Player {player.name} joined server with UUID {player.uuid}")
        
        # Return empty response (204 No Content is typical for join)
        return Response(status_code=204)
        
    except Exception as e:
        print(f"Join error for profile {profile_uuid}: {e}")
        raise HTTPException(status_code=403, detail="Invalid profile or access token")

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