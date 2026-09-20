"""Generate the AI Knowledge application icon."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "src" / "futures_kb" / "resources"
PNG_PATH = RESOURCE_DIR / "ai-knowledge.png"
ICO_PATH = RESOURCE_DIR / "ai-knowledge.ico"
SIZE = 1024


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def draw_gradient(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), "#08152F")
    pixels = image.load()
    start = (8, 21, 47)
    end = (29, 78, 216)
    for y in range(size):
        for x in range(size):
            ratio = (x + y) / (2 * (size - 1))
            pixels[x, y] = tuple(
                int(start[index] + (end[index] - start[index]) * ratio)
                for index in range(3)
            ) + (255,)
    return image


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def draw_spaced_text(
    draw: ImageDraw.ImageDraw,
    center_x: int,
    y: int,
    text: str,
    text_font: ImageFont.FreeTypeFont,
    fill: str,
    spacing: int,
) -> None:
    widths = [draw.textlength(char, font=text_font) for char in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = center_x - total / 2
    for char, width in zip(text, widths, strict=True):
        draw.text((x, y), char, font=text_font, fill=fill)
        x += width + spacing


def main() -> None:
    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)
    image = draw_gradient(SIZE)
    draw = ImageDraw.Draw(image, "RGBA")

    # Knowledge network.
    nodes = [
        (210, 250), (335, 175), (500, 225), (675, 155), (815, 270),
        (245, 820), (445, 750), (625, 825), (815, 735),
    ]
    for start, end in [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (4, 8)]:
        draw.line((nodes[start], nodes[end]), fill=(92, 201, 255, 80), width=5)
    for x, y in nodes:
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=(89, 220, 255, 145))

    # Open book.
    draw.polygon(
        [(180, 590), (500, 515), (500, 845), (180, 820)],
        fill=(244, 250, 255, 245),
        outline=(128, 221, 255, 255),
    )
    draw.polygon(
        [(500, 515), (844, 590), (844, 820), (500, 845)],
        fill=(224, 241, 255, 245),
        outline=(128, 221, 255, 255),
    )
    draw.line((500, 515, 500, 845), fill=(52, 132, 218, 220), width=10)
    for offset in (0, 50, 100):
        draw.line((235, 625 + offset, 445, 595 + offset), fill=(69, 119, 171, 100), width=7)
        draw.line((555, 595 + offset, 790, 625 + offset), fill=(69, 119, 171, 100), width=7)

    # Futures trend line.
    points = [(215, 750), (320, 700), (410, 735), (510, 640), (615, 665), (730, 565), (820, 600)]
    draw.line(points, fill=(255, 190, 72, 255), width=18, joint="curve")
    for x, y in points:
        draw.ellipse((x - 14, y - 14, x + 14, y + 14), fill=(255, 227, 143, 255), outline="#6B3D00", width=4)
    for index, (x, y) in enumerate(points):
        direction = 1 if index % 2 == 0 else -1
        draw.line((x, y - 55 * direction, x, y + 55 * direction), fill=(255, 255, 255, 220), width=9)

    # AI and KNOWLEDGE text.
    title_font = font(r"C:\Windows\Fonts\segoeuib.ttf", 238)
    sub_font = font(r"C:\Windows\Fonts\segoeuib.ttf", 64)
    draw.text((512, 215), "AI", font=title_font, fill="#FFFFFF", anchor="mm", stroke_width=3, stroke_fill="#0B2A5A")
    draw_spaced_text(draw, 512, 892, "KNOWLEDGE", sub_font, "#DDF6FF", 8)

    # Soft border.
    draw.rounded_rectangle((18, 18, 1006, 1006), radius=214, outline=(120, 222, 255, 155), width=8)

    image.putalpha(rounded_mask(SIZE, 205))
    image.save(PNG_PATH, "PNG")
    image.save(
        ICO_PATH,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(PNG_PATH)
    print(ICO_PATH)


if __name__ == "__main__":
    main()
