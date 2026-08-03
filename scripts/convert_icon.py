"""Convert PNG icon to ICO format with multiple sizes for Windows."""
from PIL import Image
import sys
import os

def convert_png_to_ico(png_path: str, ico_path: str) -> None:
    """Convert a PNG image to a multi-size ICO file."""
    img = Image.open(png_path)
    
    # Ensure RGBA mode
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Create multiple sizes for Windows (16, 32, 48, 64, 128, 256)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f"Created ICO: {ico_path}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # Find the generated PNG
    png_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not png_path:
        print("Usage: python convert_icon.py <path_to_png>")
        sys.exit(1)
    
    ico_path = os.path.join(project_root, "build", "icon.ico")
    os.makedirs(os.path.dirname(ico_path), exist_ok=True)
    convert_png_to_ico(png_path, ico_path)
