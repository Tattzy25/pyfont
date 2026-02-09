import base64
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests
API_URL = "https://api.textstudio.com/generate"


def generate_textstudio_image(
    *,
    text: str,
    style_id: str | int,
    api_key: str,
    background: str = "opaque",      # "opaque" or "transparent"
    padding: int = 5,                # percent
    quality: str = "lite",           # "lite" | "pro" | "ultra"
    format_: str = "png",            # "png" | "webp" | "jpg"
    aspect_ratio: str = "fit",       # e.g. "1:1", "16:9", or "fit"
    output: str = "binary",          # "binary" | "base64" | "dataUrl"
    timeout_s: int = 60,
) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {
        "text": text,
        "styleId": style_id,
        "background": background,
        "padding": padding,
        "quality": quality,
        "format": format_,
        "aspectRatio": aspect_ratio,
        "output": output,
    }

    resp = requests.get(API_URL, params=params, headers=headers, timeout=timeout_s)

    # If the API returns JSON errors, this will show them clearly:
    if resp.status_code != 200:
        try:
            details = resp.json()
        except ValueError:
            details = resp.text
        raise RuntimeError(f"Request failed: HTTP {resp.status_code} -> {details}")

    if output == "binary":
        # The image bytes are the body. Metadata is in headers.
        img_format = resp.headers.get("X-Image-Format", format_)
        width = resp.headers.get("X-Image-Width")
        height = resp.headers.get("X-Image-Height")
        return {
            "success": True,
            "format": img_format,
            "width": int(width) if width else None,
            "height": int(height) if height else None,
            "binary": resp.content,
        }

    # base64/dataUrl return JSON
    return resp.json()


def save_binary_image(binary: bytes, *, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(binary)


def decode_data_url(data_url: str) -> bytes:
    # format: data:image/webp;base64,AAA...
    _prefix, b64 = data_url.split(",", 1)
    return base64.b64decode(b64)


def main() -> None:
    api_key = os.getenv("TEXTSTUDIO_API_KEY")
    if not api_key:
        raise RuntimeError("Missing TEXTSTUDIO_API_KEY env var.")

    # Example: preset URL ...-261 => styleId=261
    result = generate_textstudio_image(
        text="Hello",
        style_id=261,
        api_key=api_key,
        quality="lite",
        output="binary",     # try "base64" or "dataUrl" too
        format_="webp",
        aspect_ratio="16:9",
        background="transparent",
    )

    if result.get("binary"):
        out = Path("out") / f"logo.{result.get('format') or 'png'}"
        save_binary_image(result["binary"], out_path=out)
        print(f"Saved: {out} ({result.get('width')}x{result.get('height')})")
    elif "dataUrl" in result:
        img_bytes = decode_data_url(result["dataUrl"])
        out = Path("out") / f"logo.{result.get('format') or 'png'}"
        save_binary_image(img_bytes, out_path=out)
        print(f"Saved from dataUrl: {out}")
    elif "base64" in result:
        img_bytes = base64.b64decode(result["base64"])
        out = Path("out") / f"logo.{result.get('format') or 'png'}"
        save_binary_image(img_bytes, out_path=out)
        print(f"Saved from base64: {out}")
    else:
        print("Response:", result)


if __name__ == "__main__":
    main()
