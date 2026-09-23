"""Render the Cadu MCP vector mark to browser and MCP raster sizes."""

from pathlib import Path

from PIL import Image, ImageDraw


OUTPUT = Path(__file__).resolve().parents[1] / "aicentralv2/static/images/cadu/products"
SCALE = 8
TEAL = "#03b7a0"
INK = "#14191d"


def render(size: int) -> Image.Image:
    canvas = 128 * SCALE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def point(x: int, y: int) -> tuple[int, int]:
        return x * SCALE, y * SCALE

    draw.rounded_rectangle((0, 0, canvas - 1, canvas - 1), radius=25 * SCALE, fill="#fafaf8")
    draw.polygon([point(*xy) for xy in ((44, 31), (71, 31), (48, 64), (71, 97), (44, 97), (17, 64))], fill=TEAL)
    draw.polygon([point(*xy) for xy in ((79, 31), (111, 31), (88, 64), (111, 97), (79, 97), (55, 64))], fill=INK)
    draw.line((48 * SCALE, 107 * SCALE, 80 * SCALE, 107 * SCALE), fill=TEAL, width=4 * SCALE)
    for x in (45, 83):
        draw.ellipse(((x - 4) * SCALE, 103 * SCALE, (x + 4) * SCALE, 111 * SCALE), fill=TEAL)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 48, 64, 180, 192, 512):
        render(size).save(OUTPUT / f"cadu-mcp-{size}.png", optimize=True)
    render(256).save(
        OUTPUT / "cadu-mcp-favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    # Root /favicon.ico is shared by all Cadu products. Keep its mark generic;
    # MCP pages and the MCP endpoint advertise the dedicated favicon above.
    base = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle((0, 0, 255, 255), radius=48, fill="#fafaf8")
    logo = Image.open(OUTPUT / "cadu-icon.png").convert("RGBA")
    logo = logo.resize((212, 212), Image.Resampling.LANCZOS)
    base.alpha_composite(logo, (22, 22))
    base.save(OUTPUT / "cadu-favicon.ico", format="ICO",
              sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
