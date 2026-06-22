from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from xhs_health.tools.feishu_upload import (
    FeishuApiError,
    _domain,
    _json_request,
    _load_env_file,
    _tenant_access_token,
)


def _credentials(args: argparse.Namespace) -> tuple[str, str]:
    if args.env_file:
        _load_env_file(Path(args.env_file).expanduser().resolve())

    import os

    app_id = args.app_id or os.getenv("FEISHU_APP_ID") or os.getenv("LARK_APP_ID")
    app_secret = args.app_secret or os.getenv("FEISHU_APP_SECRET") or os.getenv("LARK_APP_SECRET")
    if not app_id or not app_secret:
        raise FeishuApiError(
            "Missing FEISHU_APP_ID/FEISHU_APP_SECRET. "
            "Set them as environment variables or pass --app-id/--app-secret."
        )
    return app_id, app_secret


def _read_tokens(args: argparse.Namespace) -> list[str]:
    tokens = list(args.tokens)
    if args.tokens_file:
        path = Path(args.tokens_file).expanduser().resolve()
        if not path.exists():
            raise FeishuApiError(f"Tokens file not found: {path}")
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#"):
                tokens.append(line)
    return tokens


def transfer_owner(
    tenant_access_token: str,
    *,
    doc_token: str,
    member_id: str,
    member_type: str,
    file_type: str,
    timeout: float,
) -> dict[str, Any]:
    return _json_request(
        "POST",
        f"{_domain().rstrip('/')}/open-apis/drive/v1/permissions/{doc_token}/members/transfer_owner",
        headers={"Authorization": f"Bearer {tenant_access_token}"},
        query={"type": file_type},
        payload={"member_type": member_type, "member_id": member_id},
        timeout=timeout,
    )


def transfer_documents(args: argparse.Namespace) -> dict[str, Any]:
    tokens = _read_tokens(args)
    if not tokens:
        raise FeishuApiError("No document tokens were provided.")
    if not args.owner_id and not args.member_id:
        raise FeishuApiError("Missing --member-id.")

    member_id = args.member_id or args.owner_id
    member_type = args.member_type
    app_id, app_secret = _credentials(args)
    tenant_access_token = _tenant_access_token(app_id, app_secret, timeout=args.timeout)

    results = []
    for doc_token in tokens:
        response = transfer_owner(
            tenant_access_token,
            doc_token=doc_token,
            member_id=member_id,
            member_type=member_type,
            file_type=args.file_type,
            timeout=args.timeout,
        )
        results.append({"doc_token": doc_token, "ok": True, "response": response})
    return {"member_type": member_type, "member_id": member_id, "results": results}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transfer Feishu/Lark document ownership.")
    parser.add_argument("tokens", nargs="*", help="Document tokens to transfer.")
    parser.add_argument("--tokens-file", help="Text file with one document token per line.")
    parser.add_argument("--member-id", help="Target owner ID.")
    parser.add_argument(
        "--member-type",
        default="openid",
        choices=["openid", "userid", "email"],
        help="Target owner ID type.",
    )
    parser.add_argument("--owner-id", help="Deprecated alias for --member-id.")
    parser.add_argument("--file-type", default="docx", help="Drive permission resource type.")
    parser.add_argument("--app-id", help="Feishu/Lark app id. Defaults to FEISHU_APP_ID.")
    parser.add_argument("--app-secret", help="Feishu/Lark app secret. Defaults to FEISHU_APP_SECRET.")
    parser.add_argument("--env-file", default=".env", help="Env file to load before reading credentials.")
    parser.add_argument("--timeout", type=float, default=60, help="HTTP timeout seconds.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = transfer_documents(args)
    except FeishuApiError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "response": exc.response}, ensure_ascii=False))
        return 1

    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
