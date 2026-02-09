import json
import re
from datetime import datetime, timezone
from pathlib import Path


TAG_RE = re.compile(r"\* \[([^\]]+)\]\(/fonts/s/([^\)]+)\)")


def _escape_sql(s: str) -> str:
    return s.replace("'", "''")


def main() -> None:
    src_path = Path("FONT-URLS.txt")
    out_path = Path("textstudio_fonts_seed.sql")

    data = json.loads(src_path.read_text(encoding="utf-8"))
    results = data.get("results", [])

    rows: list[tuple[str, str, str, str | None, list[str]]] = []
    for r in results:
        url = (r.get("url") or "").strip()
        if "textstudio.com/font/" not in url:
            continue
        if "font/download?" in url:
            continue

        raw = r.get("raw_content") or ""

        # Prefer markdown heading (# Font Name)
        name = None
        m = re.search(r"^#\s+(.+?)\s*$", raw, flags=re.MULTILINE)
        if m:
            name = m.group(1).strip()
        if not name:
            # Fallback: "Some Name | PREMIUM Font" format
            m = re.search(r"^(.+?)\s*\|\s*(PREMIUM|Free)\s+Font", raw, flags=re.MULTILINE)
            if m:
                name = m.group(1).strip()
        if not name:
            name = url.rsplit("/", 1)[-1]

        license_type = "unknown"
        if "PREMIUM License" in raw or re.search(r"\|\s*PREMIUM\s+Font", raw):
            license_type = "premium"
        elif "Free license" in raw or re.search(r"\|\s*Free\s+Font", raw):
            license_type = "free"

        font_format = None
        m = re.search(r"Font format:\s*\*\*(OTF|TTF)\*\*", raw)
        if m:
            font_format = m.group(1).lower()

        categories = sorted({m.group(2).strip().lower() for m in TAG_RE.finditer(raw)})
        rows.append((url, name, license_type, font_format, categories))

    all_categories = sorted({c for *_, cats in rows for c in cats})
    mappings = [(url, c) for url, *_rest, cats in rows for c in cats]

    def fmt_nullable(v: str | None) -> str:
        return "NULL" if v is None else f"'{_escape_sql(v)}'"

    created = datetime.now(timezone.utc).isoformat()
    sql_lines: list[str] = []
    sql_lines.append(f"-- Generated from FONT-URLS.txt on {created}")
    sql_lines.append("BEGIN;")
    sql_lines.append("")

    sql_lines.append("CREATE TABLE IF NOT EXISTS textstudio_fonts (")
    sql_lines.append("  font_slug_id BIGINT,")
    sql_lines.append("  page_url TEXT PRIMARY KEY,")
    sql_lines.append("  name TEXT NOT NULL,")
    sql_lines.append("  license_type TEXT NOT NULL CHECK (license_type IN ('free','premium','unknown')),")
    sql_lines.append("  font_format TEXT NULL CHECK (font_format IN ('ttf','otf') OR font_format IS NULL),")
    sql_lines.append("  created_at TIMESTAMPTZ NOT NULL DEFAULT now()")
    sql_lines.append(");")
    sql_lines.append("")

    sql_lines.append("CREATE TABLE IF NOT EXISTS textstudio_font_categories (")
    sql_lines.append("  category_slug TEXT PRIMARY KEY,")
    sql_lines.append("  created_at TIMESTAMPTZ NOT NULL DEFAULT now()")
    sql_lines.append(");")
    sql_lines.append("")

    sql_lines.append("CREATE TABLE IF NOT EXISTS textstudio_font_category_map (")
    sql_lines.append("  page_url TEXT NOT NULL REFERENCES textstudio_fonts(page_url) ON DELETE CASCADE,")
    sql_lines.append("  category_slug TEXT NOT NULL REFERENCES textstudio_font_categories(category_slug) ON DELETE CASCADE,")
    sql_lines.append("  PRIMARY KEY (page_url, category_slug)")
    sql_lines.append(");")
    sql_lines.append("")

    sql_lines.append("CREATE INDEX IF NOT EXISTS idx_textstudio_fonts_license ON textstudio_fonts(license_type);")
    sql_lines.append("CREATE INDEX IF NOT EXISTS idx_textstudio_fonts_format ON textstudio_fonts(font_format);")
    sql_lines.append("")

    # Fonts
    sql_lines.append("-- Fonts")
    sql_lines.append("INSERT INTO textstudio_fonts (font_slug_id, page_url, name, license_type, font_format) VALUES")

    font_values: list[str] = []
    for url, name, license_type, font_format, _cats in rows:
        m = re.search(r"-(\d+)$", url)
        slug = m.group(1) if m else None
        font_values.append(
            "(" +
            (slug if slug else "NULL") +
            f",'{_escape_sql(url)}','{_escape_sql(name)}','{license_type}',{fmt_nullable(font_format)}" +
            ")"
        )

    sql_lines.append(",\n".join(font_values))
    sql_lines.append("ON CONFLICT (page_url) DO UPDATE SET")
    sql_lines.append("  name = EXCLUDED.name,")
    sql_lines.append("  license_type = EXCLUDED.license_type,")
    sql_lines.append("  font_format = EXCLUDED.font_format;")
    sql_lines.append("")

    # Categories
    sql_lines.append("-- Categories")
    if all_categories:
        sql_lines.append("INSERT INTO textstudio_font_categories (category_slug) VALUES")
        sql_lines.append(",\n".join([f"('{_escape_sql(c)}')" for c in all_categories]))
        sql_lines.append("ON CONFLICT (category_slug) DO NOTHING;")
    else:
        sql_lines.append("-- (none found)")
    sql_lines.append("")

    # Mappings
    sql_lines.append("-- Category mapping")
    if mappings:
        sql_lines.append("INSERT INTO textstudio_font_category_map (page_url, category_slug) VALUES")
        sql_lines.append(",\n".join([f"('{_escape_sql(url)}','{_escape_sql(cat)}')" for url, cat in mappings]))
        sql_lines.append("ON CONFLICT (page_url, category_slug) DO NOTHING;")
    else:
        sql_lines.append("-- (no mappings)")
    sql_lines.append("")

    sql_lines.append("COMMIT;")
    sql_lines.append("")
    sql_lines.append(
        f"-- Summary: total_fonts={len(rows)} free={sum(1 for _u,_n,l,_f,_c in rows if l=='free')} "
        f"premium={sum(1 for _u,_n,l,_f,_c in rows if l=='premium')} unknown={sum(1 for _u,_n,l,_f,_c in rows if l=='unknown')} "
        f"categories={len(all_categories)} mappings={len(mappings)}"
    )

    out_path.write_text("\n".join(sql_lines) + "\n", encoding="utf-8")
    print(f"Wrote: {out_path} ({len(rows)} fonts)")


if __name__ == "__main__":
    main()
