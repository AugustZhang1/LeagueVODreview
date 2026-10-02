"""Write the API's OpenAPI schema to frontend/openapi.json (input for `npm run gen:api`)."""

import json
from pathlib import Path

from lolreview.api import app

OUT = Path(__file__).resolve().parent.parent / "frontend" / "openapi.json"


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
