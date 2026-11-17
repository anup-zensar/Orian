"""Write the OpenAPI schema to frontend/src/api/openapi.json (no server needed).

Run from backend/:  python scripts/export_openapi.py
Then in frontend/:  npm run gen:api   (openapi-typescript -> src/api/schema.d.ts)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

OUT = BACKEND_DIR.parent / "frontend" / "src" / "api" / "openapi.json"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    OUT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
