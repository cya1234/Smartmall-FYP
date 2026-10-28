"""Dump a PPTX deck's structure and visual style so a new deck can match it."""
import sys

from pptx import Presentation
from pptx.util import Emu

EMU_PER_IN = 914400


def inch(v):
    try:
        return round(v / EMU_PER_IN, 2)
    except Exception:
        return v


def color_of(font):
    try:
        c = font.color
        if c and c.type is not None:
            if str(c.type) == 'MSO_THEME_COLOR.NOT_THEME_COLOR' or getattr(c, 'rgb', None):
                return str(c.rgb)
            if getattr(c, 'theme_color', None):
                return f"theme:{c.theme_color}"
    except Exception:
        pass
    return None


def main():
    path = sys.argv[1]
    prs = Presentation(path)
    print(f"FILE: {path}")
    print(f"SLIDE SIZE: {inch(prs.slide_width)}in x {inch(prs.slide_height)}in  "
          f"({prs.slide_width} x {prs.slide_height} EMU)")
    print(f"SLIDES: {len(prs.slides)}")
    print(f"LAYOUTS: {[l.name for l in prs.slide_layouts]}")
    print()

    # theme fonts if available
    try:
        theme = prs.slide_master.part.package.presentation_part.presentation
    except Exception:
        pass

    for i, slide in enumerate(prs.slides, 1):
        print(f"===== SLIDE {i} =====")
        print(f"  layout: {slide.slide_layout.name}")
        bg = "n/a"
        try:
            f = slide.background.fill
            bg = f"type={f.type}"
            if getattr(f, 'fore_color', None) and getattr(f.fore_color, 'rgb', None):
                bg += f" color={f.fore_color.rgb}"
        except Exception:
            pass
        print(f"  background: {bg}")

        for sh in slide.shapes:
            kind = str(sh.shape_type).split(' ')[0] if sh.shape_type else "?"
            line = (f"  - [{kind}] name={sh.name!r} "
                    f"pos=({inch(sh.left)},{inch(sh.top)}) size=({inch(sh.width)}x{inch(sh.height)})")
            if sh.has_table if hasattr(sh, 'has_table') else False:
                line += f" TABLE {len(sh.table.rows)}x{len(sh.table.columns)}"
            print(line)
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    if not p.text.strip():
                        continue
                    runs = []
                    for r in p.runs:
                        if not r.text.strip():
                            continue
                        f_ = r.font
                        runs.append(
                            f"{r.text[:60]!r}(sz={f_.size.pt if f_.size else None},"
                            f"b={f_.bold},col={color_of(f_)})"
                        )
                    if runs:
                        print(f"        p(align={p.alignment}): " + " | ".join(runs))
            if sh.has_table if hasattr(sh, 'has_table') else False:
                for row in sh.table.rows:
                    print("        ROW: " + " | ".join(c.text[:24] for c in row.cells))
            if sh.shape_type and 'PICTURE' in str(sh.shape_type):
                try:
                    print(f"        image: {sh.image.filename} {sh.image.size} {sh.image.content_type}")
                except Exception as e:
                    print(f"        image: (unreadable {e})")
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            print(f"  NOTES: {slide.notes_slide.notes_text_frame.text[:200]!r}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
