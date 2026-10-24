"""Print a dev sign-in token, so protected endpoints can be called locally before the web app exists.

    .venv/Scripts/python.exe -m app.cli.dev_token --email priya@example.com
    curl -H "Authorization: Bearer <token>" http://localhost:8000/v1/me

Works only when the API runs with AUTH_MODE=dev (the default locally); staging and production reject these tokens.
"""

from __future__ import annotations

import argparse
from datetime import timedelta

from app.core.auth import mint_dev_token
from app.core.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--subject", help="stable user id (default: dev|<email>)")
    parser.add_argument("--hours", type=float, default=12, help="how long the token stays valid")
    args = parser.parse_args()

    settings = get_settings()
    if settings.auth_mode != "dev":
        parser.error(f"AUTH_MODE is {settings.auth_mode!r}; dev tokens only work with AUTH_MODE=dev")

    token = mint_dev_token(
        settings.auth_dev_secret.get_secret_value(),
        subject=args.subject or f"dev|{args.email.lower()}",
        email=args.email,
        audience=settings.auth_audience,
        ttl=timedelta(hours=args.hours),
    )
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
