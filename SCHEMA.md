### Database schema reference (Neon Postgres)

This project currently uses two groups of tables:

1) **Fonts catalog tables** (created/seeded by `textstudio_fonts_seed.sql`)
2) **Text styles catalog table** (used by the web app endpoint `GET /styles` in `app.py`)

This file is meant to be a quick “AI dev + human” reference to what exists and how it relates.

---

### Fonts catalog (from `textstudio_fonts_seed.sql`)

#### `textstudio_fonts`
Stores one row per TextStudio **font detail page**.

```sql
CREATE TABLE IF NOT EXISTS textstudio_fonts (
  font_slug_id BIGINT,
  page_url TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  license_type TEXT NOT NULL CHECK (license_type IN ('free','premium','unknown')),
  font_format TEXT NULL CHECK (font_format IN ('ttf','otf') OR font_format IS NULL),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_textstudio_fonts_license ON textstudio_fonts(license_type);
CREATE INDEX IF NOT EXISTS idx_textstudio_fonts_format ON textstudio_fonts(font_format);
```

**Columns**
- `font_slug_id`: numeric ID parsed from the end of the font page URL (e.g. `/font/source-sans-pro-683` → `683`).
- `page_url`: canonical font page URL (primary key).
- `name`: font display name parsed from the scraped page.
- `license_type`: `free` / `premium` / `unknown` based on scraped page text.
- `font_format`: `ttf` / `otf` if detected, otherwise `NULL`.
- `created_at`: insertion timestamp.

#### `textstudio_font_categories`
Stores unique category/tag slugs (e.g. `halloween`, `sans-serif`).

```sql
CREATE TABLE IF NOT EXISTS textstudio_font_categories (
  category_slug TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### `textstudio_font_category_map`
Many-to-many mapping between fonts and categories.

```sql
CREATE TABLE IF NOT EXISTS textstudio_font_category_map (
  page_url TEXT NOT NULL REFERENCES textstudio_fonts(page_url) ON DELETE CASCADE,
  category_slug TEXT NOT NULL REFERENCES textstudio_font_categories(category_slug) ON DELETE CASCADE,
  PRIMARY KEY (page_url, category_slug)
);
```

**Relationship**
- `textstudio_fonts (1) -> (many) textstudio_font_category_map (many) -> (1) textstudio_font_categories`

---

### Text styles catalog (used by the app)

`app.py` calls your Neon PostgREST endpoint for `textstudio_styles`.

At minimum the app expects these columns:
- `style_id` (text)
- `name` (text)
- `active` (boolean)
- `sort_order` (integer; optional but used for ordering)

Recommended schema:

```sql
CREATE TABLE IF NOT EXISTS textstudio_styles (
  style_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  source_url TEXT NULL,
  editor_type TEXT NOT NULL DEFAULT 'classic',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INTEGER NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_textstudio_styles_active ON textstudio_styles(active);
CREATE INDEX IF NOT EXISTS idx_textstudio_styles_sort_order ON textstudio_styles(sort_order);
```

**Notes**
- `style_id` is stored as `TEXT` on purpose so it can hold both numeric gallery IDs (e.g. `261`) and UUID `userPresetId` values.
- `source_url` is optional but useful for traceability (the human-facing TextStudio page you got it from).

---

### Is `textstudio_fonts_seed.sql` “already a schema”?

It’s both:
- It contains the **schema** (`CREATE TABLE ...`) for the fonts tables.
- It also contains the **seed data** (`INSERT INTO ...`) for fonts, categories, and mappings.

So if you want a pure schema-only doc, use this `SCHEMA.md` file as the reference.
