from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_DOMAIN = "https://open.feishu.cn"
MAX_SIMPLE_UPLOAD_BYTES = 20 * 1024 * 1024


class FeishuApiError(RuntimeError):
    def __init__(self, message: str, *, response: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.response = response


def _json_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    query: dict[str, str] | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    if query:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(query)}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        request_headers["Content-Type"] = "application/json; charset=utf-8"
    request = Request(url, data=data, headers=request_headers, method=method)
    return _send_json(request, timeout)


def _multipart_request(
    url: str,
    *,
    headers: dict[str, str],
    fields: dict[str, str],
    file_path: Path,
    timeout: float = 60,
) -> dict[str, Any]:
    boundary = f"----xhs-health-{uuid.uuid4().hex}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        (
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    body.extend(file_path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    request_headers = {
        "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        **headers,
    }
    request = Request(url, data=bytes(body), headers=request_headers, method="POST")
    return _send_json(request, timeout)


def _send_json(request: Request, timeout: float) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise FeishuApiError(f"HTTP {exc.code}: {raw}") from exc
    except URLError as exc:
        raise FeishuApiError(f"Network error: {exc.reason}") from exc

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FeishuApiError(f"Non-JSON response: {raw[:500]}") from exc

    code = result.get("code", 0)
    if code != 0:
        raise FeishuApiError(f"Feishu API error {code}: {result.get('msg')}", response=result)
    return result


def _env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def _domain() -> str:
    return os.getenv("FEISHU_DOMAIN") or os.getenv("LARK_DOMAIN") or DEFAULT_DOMAIN


def _tenant_access_token(app_id: str, app_secret: str, *, timeout: float) -> str:
    response = _json_request(
        "POST",
        f"{_domain().rstrip('/')}/open-apis/auth/v3/tenant_access_token/internal",
        payload={"app_id": app_id, "app_secret": app_secret},
        timeout=timeout,
    )
    token = response.get("tenant_access_token")
    if not token:
        raise FeishuApiError("No tenant_access_token returned.", response=response)
    return str(token)


def _upload_source_file(
    token: str,
    file_path: Path,
    *,
    folder_token: str,
    source_upload: str,
    timeout: float,
) -> str:
    size = file_path.stat().st_size
    if size > MAX_SIMPLE_UPLOAD_BYTES:
        raise FeishuApiError(
            f"File is larger than {MAX_SIMPLE_UPLOAD_BYTES} bytes; simple upload is not supported."
        )

    if source_upload == "file":
        url = f"{_domain().rstrip('/')}/open-apis/drive/v1/files/upload_all"
        fields = {
            "file_name": file_path.name,
            "parent_type": "explorer",
            "parent_node": folder_token,
            "size": str(size),
        }
    else:
        url = f"{_domain().rstrip('/')}/open-apis/drive/v1/medias/upload_all"
        fields = {
            "file_name": file_path.name,
            "parent_type": "ccm_import_open",
            "size": str(size),
        }

    response = _multipart_request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        fields=fields,
        file_path=file_path,
        timeout=timeout,
    )
    file_token = response.get("data", {}).get("file_token")
    if not file_token:
        raise FeishuApiError("No file_token returned after upload.", response=response)
    return str(file_token)


def _default_doc_type(file_path: Path) -> str:
    suffix = file_path.suffix.lower().lstrip(".")
    if suffix in {"csv", "xls", "xlsx"}:
        return "sheet"
    return "docx"


def _create_import_task(
    token: str,
    file_path: Path,
    file_token: str,
    *,
    doc_type: str,
    file_name: str,
    folder_token: str,
    timeout: float,
) -> str:
    response = _json_request(
        "POST",
        f"{_domain().rstrip('/')}/open-apis/drive/v1/import_tasks",
        headers={"Authorization": f"Bearer {token}"},
        payload={
            "file_extension": file_path.suffix.lower().lstrip("."),
            "file_token": file_token,
            "type": doc_type,
            "file_name": file_name,
            "point": {"mount_type": 1, "mount_key": folder_token},
        },
        timeout=timeout,
    )
    ticket = response.get("data", {}).get("ticket")
    if not ticket:
        raise FeishuApiError("No import ticket returned.", response=response)
    return str(ticket)


def _poll_import_task(
    token: str,
    ticket: str,
    *,
    attempts: int,
    interval: float,
    timeout: float,
) -> dict[str, Any]:
    last_response: dict[str, Any] | None = None
    for _ in range(attempts):
        response = _json_request(
            "GET",
            f"{_domain().rstrip('/')}/open-apis/drive/v1/import_tasks/{ticket}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        data = response.get("data", {})
        result = data.get("result") or {}
        job_status = data.get("job_status")
        if result.get("url") or result.get("token"):
            return data
        if job_status in {0, "0", "success", "succeeded"}:
            return data
        if job_status in {2, "2", "failed", "fail"}:
            raise FeishuApiError("Import task failed.", response=response)
        last_response = response
        time.sleep(interval)

    raise FeishuApiError("Import task did not finish before timeout.", response=last_response)


def upload_document(args: argparse.Namespace) -> dict[str, Any]:
    if args.env_file:
        _load_env_file(Path(args.env_file).expanduser().resolve())

    app_id = args.app_id or _env("FEISHU_APP_ID", "LARK_APP_ID")
    app_secret = args.app_secret or _env("FEISHU_APP_SECRET", "LARK_APP_SECRET")
    folder_token = args.folder_token
    if folder_token is None:
        folder_token = _env("FEISHU_FOLDER_TOKEN", "LARK_FOLDER_TOKEN") or ""

    if not app_id or not app_secret:
        raise FeishuApiError(
            "Missing FEISHU_APP_ID/FEISHU_APP_SECRET. "
            "Set them as environment variables or pass --app-id/--app-secret."
        )

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        raise FeishuApiError(f"File not found: {file_path}")
    if not file_path.suffix:
        raise FeishuApiError("The source file must have an extension, for example .md.")

    doc_type = args.type or _default_doc_type(file_path)
    file_name = args.title or file_path.stem
    token = _tenant_access_token(app_id, app_secret, timeout=args.timeout)
    file_token = _upload_source_file(
        token,
        file_path,
        folder_token=folder_token,
        source_upload=args.source_upload,
        timeout=args.timeout,
    )
    ticket = _create_import_task(
        token,
        file_path,
        file_token,
        doc_type=doc_type,
        file_name=file_name,
        folder_token=folder_token,
        timeout=args.timeout,
    )
    task = _poll_import_task(
        token,
        ticket,
        attempts=args.poll_attempts,
        interval=args.poll_interval,
        timeout=args.timeout,
    )

    result = task.get("result") or {}
    return {
        "source": str(file_path),
        "file_name": file_name,
        "type": doc_type,
        "folder_token": folder_token or None,
        "source_upload": args.source_upload,
        "file_token": file_token,
        "ticket": ticket,
        "job_status": task.get("job_status"),
        "doc_token": result.get("token"),
        "doc_url": result.get("url"),
        "raw_result": result,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload a local file and import it as a Feishu/Lark cloud document."
    )
    parser.add_argument("file", help="Local file path, for example report.md")
    parser.add_argument("--title", help="Imported document title. Defaults to file stem.")
    parser.add_argument("--type", choices=["docx", "sheet", "bitable"], help="Target cloud doc type.")
    parser.add_argument("--folder-token", help="Target Drive folder token. Defaults to FEISHU_FOLDER_TOKEN.")
    parser.add_argument(
        "--source-upload",
        choices=["media", "file"],
        default="file",
        help="Upload API used before import. Defaults to file.",
    )
    parser.add_argument("--app-id", help="Feishu/Lark app id. Defaults to FEISHU_APP_ID.")
    parser.add_argument("--app-secret", help="Feishu/Lark app secret. Defaults to FEISHU_APP_SECRET.")
    parser.add_argument("--env-file", default=".env", help="Env file to load before reading credentials.")
    parser.add_argument("--timeout", type=float, default=60, help="HTTP timeout seconds.")
    parser.add_argument("--poll-attempts", type=int, default=30, help="Import polling attempts.")
    parser.add_argument("--poll-interval", type=float, default=2, help="Seconds between polls.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = upload_document(args)
    except FeishuApiError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "response": exc.response}, ensure_ascii=False))
        return 1

    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
