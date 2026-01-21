from PIL import Image

def generate_avatar(skin_path, output_path, width, height):
    try:
        with Image.open(skin_path) as img:
            img = img.convert("RGBA")

            # --- Minecraft Skin Layout Coordinates (64x64 base) ---
            # These are the standard pixel coordinates for a 64x64 skin.
            # (x_start, y_start, width, height)
            FACE_FRONT = (8, 8, 8, 8)
            HELMET_FRONT = (40, 8, 8, 8)

            # Calculate scaling factor based on the skin's width relative to 64px.
            scale_factor = width / 64

            # --- Calculate dynamic crop coordinates ---
            # Inner Head (face)
            face_x1 = int(FACE_FRONT[0] * scale_factor)
            face_y1 = int(FACE_FRONT[1] * scale_factor)
            face_x2 = int((FACE_FRONT[0] + FACE_FRONT[2]) * scale_factor)
            face_y2 = int((FACE_FRONT[1] + FACE_FRONT[3]) * scale_factor)

            # Head Overlay (helmet)
            helmet_x1 = int(HELMET_FRONT[0] * scale_factor)
            helmet_y1 = int(HELMET_FRONT[1] * scale_factor)
            helmet_x2 = int((HELMET_FRONT[0] + HELMET_FRONT[2]) * scale_factor)
            helmet_y2 = int((HELMET_FRONT[1] + HELMET_FRONT[3]) * scale_factor)

            # --- Perform Cropping ---
            # Crop the inner head (face) area
            head = img.crop((face_x1, face_y1, face_x2, face_y2))
            
            # Apply head overlay (helmet) if the skin format supports it (height >= 64)
            if height >= 64:
                overlay = img.crop((helmet_x1, helmet_y1, helmet_x2, helmet_y2))
                # Resize overlay to match head size before pasting to ensure correct alignment
                overlay = overlay.resize(head.size, Image.NEAREST)
                head.paste(overlay, (0, 0), overlay) # Paste overlay at (0,0) relative to the cropped head
            
            # Resize the final avatar for a clearer view, maintaining the pixelated look
            avatar = head.resize((128, 128), Image.NEAREST)
            
            avatar.save(output_path)

    except Exception as e:
        pass # Suppress error logging in production, or use a proper logger
