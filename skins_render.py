from PIL import Image

def generate_avatar(skin_path, output_path):
    try:
        with Image.open(skin_path) as img:
            # Force convert to RGBA to standardize the image and fix transparency issues
            img = img.convert("RGBA")

            # A standard skin is 64x64, but legacy skins can be 64x32.
            # The head area is the same for both.
            if img.size not in [(64, 64), (64, 32)]:
                print(f"Warning: Non-standard skin size {img.size}. Avatar may not be correct.")

            # Crop the head area (8, 8) to (16, 16)
            head = img.crop((8, 8, 16, 16))
            
            # The helmet/overlay layer only exists on 64x64 skins.
            if img.size == (64, 64):
                # Crop the helmet/overlay area (40, 8) to (48, 16)
                overlay = img.crop((40, 8, 48, 16))
                
                # Paste the overlay onto the head using its own alpha channel as the mask
                head.paste(overlay, (0, 0), overlay)
            
            # Resize for a clearer view, maintaining the pixelated look
            avatar = head.resize((128, 128), Image.NEAREST)
            
            avatar.save(output_path)
    except Exception as e:
        print(f"Error generating avatar: {e}")
