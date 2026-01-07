#!/usr/bin/env python3
"""
Generate app icons for Cortona Electron app
"""

from PIL import Image, ImageDraw
import os

# Ensure assets directory exists
os.makedirs('assets', exist_ok=True)

def create_main_icon(size=1024):
    """Create the main app icon - a stylized microphone/wave"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle with gradient effect (dark purple/blue)
    center = size // 2
    radius = size // 2 - 20
    
    # Draw gradient background (multiple circles)
    for i in range(radius, 0, -2):
        # Gradient from deep purple to cyan
        ratio = i / radius
        r = int(20 + (0 - 20) * (1 - ratio))
        g = int(15 + (180 - 15) * (1 - ratio) * 0.3)
        b = int(40 + (220 - 40) * (1 - ratio))
        draw.ellipse(
            [center - i, center - i, center + i, center + i],
            fill=(r, g, b, 255)
        )
    
    # Draw a microphone shape
    mic_width = size // 5
    mic_height = size // 3
    mic_x = center - mic_width // 2
    mic_y = center - mic_height // 2 - size // 12
    
    # Microphone body (rounded rectangle approximation with ellipse + rectangle)
    mic_radius = mic_width // 2
    
    # Top rounded part
    draw.ellipse(
        [mic_x, mic_y, mic_x + mic_width, mic_y + mic_width],
        fill=(0, 245, 212, 255)  # Cyan accent
    )
    
    # Body rectangle
    draw.rectangle(
        [mic_x, mic_y + mic_radius, mic_x + mic_width, mic_y + mic_height],
        fill=(0, 245, 212, 255)
    )
    
    # Bottom rounded part
    draw.ellipse(
        [mic_x, mic_y + mic_height - mic_radius, mic_x + mic_width, mic_y + mic_height + mic_radius],
        fill=(0, 245, 212, 255)
    )
    
    # Microphone stand (curved line)
    stand_top = mic_y + mic_height + mic_radius // 2
    stand_width = int(mic_width * 1.5)
    stand_x = center - stand_width // 2
    
    # Draw arc for stand
    draw.arc(
        [stand_x, stand_top - mic_width // 2, stand_x + stand_width, stand_top + mic_width],
        start=0, end=180,
        fill=(0, 245, 212, 255),
        width=size // 40
    )
    
    # Vertical line down
    line_height = size // 8
    draw.rectangle(
        [center - size // 80, stand_top + mic_width // 2, center + size // 80, stand_top + mic_width // 2 + line_height],
        fill=(0, 245, 212, 255)
    )
    
    # Base
    base_width = mic_width
    draw.rectangle(
        [center - base_width // 2, stand_top + mic_width // 2 + line_height, 
         center + base_width // 2, stand_top + mic_width // 2 + line_height + size // 40],
        fill=(0, 245, 212, 255)
    )
    
    # Add some sound waves on the sides
    wave_color = (0, 245, 212, 150)
    for i, offset in enumerate([60, 100, 140]):
        alpha = 200 - i * 50
        wave_color = (0, 245, 212, alpha)
        # Left wave
        draw.arc(
            [center - mic_width - offset, mic_y + mic_height // 4,
             center - mic_width // 2, mic_y + mic_height - mic_height // 4],
            start=120, end=240,
            fill=wave_color,
            width=size // 60
        )
        # Right wave
        draw.arc(
            [center + mic_width // 2, mic_y + mic_height // 4,
             center + mic_width + offset, mic_y + mic_height - mic_height // 4],
            start=-60, end=60,
            fill=wave_color,
            width=size // 60
        )
    
    return img


def create_tray_icon(size=18):
    """Create menubar tray icon - template image (black on transparent)"""
    # Create at 2x for retina, will be 36x36
    actual_size = size * 2
    img = Image.new('RGBA', (actual_size, actual_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = actual_size // 2
    
    # Simple microphone icon in black (for template image)
    mic_width = actual_size // 3
    mic_height = actual_size // 2
    mic_x = center - mic_width // 2
    mic_y = 4
    
    # Mic body
    draw.rounded_rectangle(
        [mic_x, mic_y, mic_x + mic_width, mic_y + mic_height],
        radius=mic_width // 2,
        fill=(0, 0, 0, 255)
    )
    
    # Stand arc
    stand_y = mic_y + mic_height + 2
    draw.arc(
        [mic_x - 4, stand_y - mic_height // 3, mic_x + mic_width + 4, stand_y + 6],
        start=0, end=180,
        fill=(0, 0, 0, 255),
        width=2
    )
    
    # Vertical stem
    draw.rectangle(
        [center - 1, stand_y + 3, center + 1, stand_y + 8],
        fill=(0, 0, 0, 255)
    )
    
    # Base
    draw.rectangle(
        [center - 4, stand_y + 7, center + 4, stand_y + 9],
        fill=(0, 0, 0, 255)
    )
    
    # Resize to actual size (for non-retina)
    img_small = img.resize((size, size), Image.Resampling.LANCZOS)
    
    return img, img_small


def create_iconset(main_icon):
    """Create all sizes needed for .iconset"""
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    iconset_dir = 'assets/icon.iconset'
    os.makedirs(iconset_dir, exist_ok=True)
    
    for size in sizes:
        # Regular
        resized = main_icon.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(f'{iconset_dir}/icon_{size}x{size}.png')
        
        # @2x (except for 1024 which is already 2x of 512)
        if size <= 512:
            size_2x = size * 2
            resized_2x = main_icon.resize((size_2x, size_2x), Image.Resampling.LANCZOS)
            resized_2x.save(f'{iconset_dir}/icon_{size}x{size}@2x.png')
    
    return iconset_dir


if __name__ == '__main__':
    print("🎨 Creating Cortona icons...")
    
    # Main app icon
    print("  → Creating main icon (1024x1024)...")
    main_icon = create_main_icon(1024)
    main_icon.save('assets/icon.png')
    print("    ✅ assets/icon.png")
    
    # Tray icon (template)
    print("  → Creating tray icon (18x18)...")
    tray_2x, tray_1x = create_tray_icon(18)
    tray_1x.save('assets/trayTemplate.png')
    tray_2x.save('assets/trayTemplate@2x.png')
    print("    ✅ assets/trayTemplate.png")
    print("    ✅ assets/trayTemplate@2x.png")
    
    # Create iconset for .icns
    print("  → Creating iconset...")
    iconset_dir = create_iconset(main_icon)
    print(f"    ✅ {iconset_dir}/")
    
    # Convert to .icns using iconutil (macOS only)
    print("  → Converting to .icns...")
    result = os.system(f'iconutil -c icns {iconset_dir} -o assets/icon.icns 2>/dev/null')
    if result == 0:
        print("    ✅ assets/icon.icns")
        # Clean up iconset
        import shutil
        shutil.rmtree(iconset_dir)
    else:
        print("    ⚠️  iconutil not available, keeping iconset folder")
    
    print("\n✅ All icons created in assets/")

