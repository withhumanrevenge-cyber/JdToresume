"""Write the API's OpenAPI schema to a file; the web app's TypeScript types are generated from it.

    .venv/Scripts/python.exe -m app.cli.openapi packages/api-types/openapi.json
    corepack pnpm api-types

Built with fixed local settings (dev sign-in included), so the output doesn't depend on anyone's .env.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    schema = create_app(Settings(_env_file=None, environment="local", auth_mode="dev")).openapi()
    # Always "\n": CI regenerates this file on Linux and fails if it differs from the committed copy.
    args.output.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {args.output} ({len(schema['paths'])} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
