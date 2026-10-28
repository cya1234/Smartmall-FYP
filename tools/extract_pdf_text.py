"""Extract text from a PDF into a UTF-8 text file, page by page."""
import sys

from pypdf import PdfReader


def main():
    if len(sys.argv) < 3:
        print("usage: extract_pdf_text.py <input.pdf> <output.txt>")
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    reader = PdfReader(src)
    pages = len(reader.pages)
    chunks = []
    empty = 0
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception as e:  # noqa: BLE001
            txt = f"[extract error: {e}]"
        if not txt.strip():
            empty += 1
        chunks.append(f"\n\n===== PAGE {i+1}/{pages} =====\n{txt}")
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write("".join(chunks))
    total = sum(len(c) for c in chunks)
    print(f"  pages: {pages}")
    print(f"  pages with no text layer: {empty}")
    print(f"  extracted chars: {total}")
    print(f"  wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
