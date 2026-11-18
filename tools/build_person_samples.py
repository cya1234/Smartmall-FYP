"""Build the sample-person set used by the virtual try-on page.

Two sources, both already on disk:

  * the four demo photos that ship with CatVTON  -> proper full-body studio shots
  * front-facing model shots from the catalogue   -> already 3:4, so no cropping

The point is that a visitor can try the feature without photographing themselves, which
matters at a demo table and for anyone unwilling to upload a picture of themselves.

    python tools/build_person_samples.py
"""
import json
import os
import shutil

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "public", "assets", "persons")
VENDOR = os.path.join(ROOT, "ai-service", "vendor", "CatVTON", "resource",
                      "demo", "example", "condition", "person")
PRODUCTS = os.path.join(ROOT, "public", "assets", "products")

# The four CatVTON demo people, plus catalogue model shots that show a full torso.
VENDOR_NAMES = {
    "baumu30483223c3_1719437121402_2-0._QL90_UX564_V12524t6_.jpg": ("範例人物 1", "Sample 1"),
    "jbeeq301271a569_1719429971246_2-0._QL90_UX564_V12524t6_.jpg": ("範例人物 2", "Sample 2"),
    "mison407622250d_1719258948458_2-0._QL90_UX564_V12524t6_.jpg": ("範例人物 3", "Sample 3"),
    "mothr22044226e8_1718142523286_2-0._QL90_UX564_V12524t6_.jpg": ("範例人物 4", "Sample 4"),
}
CATALOGUE_NAMES = {
    "p001": ("模特兒 A", "Model A"),
    "p002": ("模特兒 B", "Model B"),
    "p003": ("模特兒 C", "Model C"),
    "p005": ("模特兒 D", "Model D"),
    "p006": ("模特兒 E", "Model E"),
    "p035": ("模特兒 F", "Model F"),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []

    for i, (src, (zh, en)) in enumerate(VENDOR_NAMES.items(), start=1):
        path = os.path.join(VENDOR, src)
        if not os.path.exists(path):
            print(f"  skip missing: {src}")
            continue
        name = f"person-{i:02d}.jpg"
        # Normalise to JPEG so the browser cache and the data-URL path are predictable.
        Image.open(path).convert("RGB").save(os.path.join(OUT, name), "JPEG", quality=90)
        manifest.append({"file": name, "zh": zh, "en": en, "source": "catvton-demo"})

    for j, (pid, (zh, en)) in enumerate(CATALOGUE_NAMES.items(), start=len(manifest) + 1):
        src = os.path.join(PRODUCTS, f"{pid}.jpg")
        if not os.path.exists(src):
            print(f"  skip missing: {pid}")
            continue
        name = f"person-{j:02d}.jpg"
        Image.open(src).convert("RGB").save(os.path.join(OUT, name), "JPEG", quality=90)
        manifest.append({"file": name, "zh": zh, "en": en, "source": pid})

    with open(os.path.join(OUT, "persons.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    total = sum(os.path.getsize(os.path.join(OUT, m["file"])) for m in manifest)
    print(f"  {len(manifest)} sample people, {total / 1024:.0f} KB")
    for m in manifest:
        print(f"    {m['file']}  {m['zh']}")


if __name__ == "__main__":
    main()
