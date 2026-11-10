from PIL import Image, ImageDraw, ImageFilter

from backend.services.quality_service import assess_image_quality


def test_assess_image_quality_accepts_clear_white_document_page():
    img = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(img)
    for y in range(120, 800, 70):
        draw.line((80, y, 1120, y), fill=(220, 220, 220), width=2)
    for i, label in enumerate(["Name", "Age", "BP", "Weight", "Vision"]):
        draw.text((100, 100 + i * 110), label, fill=(30, 30, 30))

    clear_page = img.filter(ImageFilter.GaussianBlur(0.5))
    result = assess_image_quality(clear_page)

    assert result["ok"] is True, result
