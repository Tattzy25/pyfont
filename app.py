import os
import time
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

# Load .env if it exists (for local development)
if os.path.exists("EnvironmentVariables.env"):
    load_dotenv("EnvironmentVariables.env")

app = Flask(__name__)

# Fallback for Vercel environment variables
API_KEY = os.getenv("TEXTSTUDIO_API_KEY")
TEXTSTUDIO_URL = "https://api.textstudio.com/generate"

# Neon PostgREST (Neon Data API) config.
# Example base: https://<project>.apirest.<region>.aws.neon.tech/<db>/rest/v1
NEON_REST_URL = os.getenv("NEON_REST_URL")
NEON_REST_API_KEY = os.getenv("NEON_REST_API_KEY")

_NEON_TIMEOUT_S = 15


def _neon_headers() -> dict:
    # PostgREST deployments commonly accept either `apikey` and/or `Authorization: Bearer`.
    # We send both when provided.
    headers = {"Accept": "application/json"}
    if NEON_REST_API_KEY:
        headers["apikey"] = NEON_REST_API_KEY
        headers["Authorization"] = f"Bearer {NEON_REST_API_KEY}"
    return headers


def _neon_get(path: str, *, params: dict | None = None):
    if not NEON_REST_URL:
        raise RuntimeError(
            "Missing NEON_REST_URL. Set it to your Neon PostgREST base, e.g. "
            "https://<project>.apirest.<region>.aws.neon.tech/<db>/rest/v1"
        )

    url = NEON_REST_URL.rstrip("/") + "/" + path.lstrip("/")
    resp = requests.get(url, params=params or {}, headers=_neon_headers(), timeout=_NEON_TIMEOUT_S)
    # If the REST endpoint is protected and no key is supplied, you'll usually get 401/403.
    if resp.status_code >= 400:
        try:
            details = resp.json()
        except ValueError:
            details = resp.text
        raise RuntimeError(f"Neon REST request failed: HTTP {resp.status_code} -> {details}")
    return resp.json()

# Very small in-process cache for preview images (Vercel instances are ephemeral).
# Key: (style_id, text) -> {"data": <json>, "ts": <epoch_seconds>}
_preview_cache: dict[tuple[str, str], dict] = {}
_PREVIEW_CACHE_TTL_SECONDS = 60 * 60


def _cache_get(style_id: str, text: str):
    key = (style_id, text)
    entry = _preview_cache.get(key)
    if not entry:
        return None
    if time.time() - entry["ts"] > _PREVIEW_CACHE_TTL_SECONDS:
        _preview_cache.pop(key, None)
        return None
    return entry["data"]


def _cache_set(style_id: str, text: str, data):
    _preview_cache[(style_id, text)] = {"data": data, "ts": time.time()}

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/styles', methods=['GET'])
def styles():
    # Expect a table with at least: style_id (text), name (text), active (bool/int), sort_order (int)
    # The UI expects: [{ id, name }]
    try:
        rows = _neon_get(
            "textstudio_styles",
            params={
                "select": "style_id,name",
                "active": "eq.true",
                "order": "sort_order.asc.nullslast,name.asc",
            },
        )
        styles = [
            {"id": r.get("style_id"), "name": r.get("name")}
            for r in (rows or [])
            if r.get("style_id") and r.get("name")
        ]
        return jsonify({"success": True, "styles": styles})
    except Exception as e:
        return jsonify(
            {
                "success": False,
                "error": str(e),
                "hint": "Ensure NEON_REST_URL/NEON_REST_API_KEY are set and table textstudio_styles exists.",
            }
        ), 500


@app.route('/fonts', methods=['GET'])
def fonts():
    # Read-only font catalog from Neon.
    # Tables created by `textstudio_fonts_seed.sql`:
    # - textstudio_fonts(page_url, name, license_type, font_format, ...)
    try:
        limit = request.args.get("limit", "200")
        license_type = request.args.get("license")  # optional: free|premium

        params = {
            "select": "page_url,name,license_type,font_format",
            "order": "license_type.asc,name.asc",
            "limit": limit,
        }
        if license_type:
            params["license_type"] = f"eq.{license_type}"

        rows = _neon_get("textstudio_fonts", params=params)

        fonts_out = [
            {
                "pageUrl": r.get("page_url"),
                "name": r.get("name"),
                "licenseType": r.get("license_type"),
                "format": r.get("font_format"),
            }
            for r in (rows or [])
            if r.get("page_url") and r.get("name")
        ]

        return jsonify({"success": True, "fonts": fonts_out})
    except Exception as e:
        return jsonify(
            {
                "success": False,
                "error": str(e),
                "hint": "Ensure NEON_REST_URL/NEON_REST_API_KEY are set and fonts tables exist (textstudio_fonts...).",
            }
        ), 500


@app.route('/preview', methods=['GET'])
def preview():
    style_id = request.args.get('styleId')
    text = request.args.get('text', 'ABC')

    if not style_id:
        return jsonify({"success": False, "error": "Missing styleId"}), 400

    cached = _cache_get(str(style_id), text)
    if cached:
        return jsonify(cached)

    payload = {"text": text, "styleId": style_id}
    # Reuse the same generation logic/contract as the UI.
    with app.test_request_context(json=payload):
        resp = generate()

    # `generate()` may return (json, status) or a Response.
    if isinstance(resp, tuple):
        body, status = resp
        if status != 200:
            return resp
        data = body.get_json() if hasattr(body, "get_json") else body
    else:
        data = resp.get_json() if hasattr(resp, "get_json") else resp

    # Only cache successful previews with a dataUrl.
    if isinstance(data, dict) and data.get("success") and data.get("dataUrl"):
        _cache_set(str(style_id), text, data)
    return jsonify(data)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    text = data.get('text')
    style_id = data.get('styleId')

    if not text or not style_id:
        return jsonify({"success": False, "error": "Missing text or styleId"}), 400

    params = {
        'text': text,
        'styleId': style_id,
        'background': 'transparent',
        'format': 'png',
        'quality': 'lite',
        'output': 'dataUrl',
        'padding': 5,
        'aspectRatio': 'fit'
    }

    headers = {
        'Authorization': f'Bearer {API_KEY}'
    }

    try:
        response = requests.get(TEXTSTUDIO_URL, params=params, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error calling TextStudio API: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    from waitress import serve
    print("Starting production server on http://0.0.0.0:5000")
    serve(app, host='0.0.0.0', port=5000)
