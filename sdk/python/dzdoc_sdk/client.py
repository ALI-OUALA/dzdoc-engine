from __future__ import annotations

import json
import mimetypes
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class DzDocError(RuntimeError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"DzDoc API {status}: {detail}")
        self.status = status
        self.detail = detail


class DzDocClient:
    def __init__(self, api_key: str, *, base_url: str = "http://127.0.0.1:8000") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def submit(
        self,
        path: str | Path,
        *,
        capability: str = "cpu",
        idempotency_key: str | None = None,
    ) -> Any:
        source = Path(path)
        boundary = "dzdoc-" + uuid.uuid4().hex
        media = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        prefix = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{source.name}"\r\nContent-Type: {media}\r\n\r\n'
        ).encode()
        body = prefix + source.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        return self._request(
            f"/v1/documents?capability={capability}",
            method="POST",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Idempotency-Key": idempotency_key or str(uuid.uuid4()),
            },
        )

    def job(self, job_id: str) -> Any:
        return self._request(f"/v1/jobs/{job_id}")

    def jobs(self) -> list[dict[str, Any]]:
        return self._request("/v1/jobs")["items"]

    def result(self, document_id: str) -> Any:
        return self._request(f"/v1/documents/{document_id}/result")

    def correct(
        self,
        document_id: str,
        *,
        target_id: str,
        previous_text: str,
        corrected_text: str,
        reason: str | None = None,
    ) -> Any:
        return self._request(
            f"/v1/documents/{document_id}/corrections",
            method="POST",
            data=json.dumps(
                {
                    "target_id": target_id,
                    "previous_text": previous_text,
                    "corrected_text": corrected_text,
                    "reason": reason,
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )

    def delete(self, document_id: str) -> None:
        self._request(f"/v1/documents/{document_id}", method="DELETE")

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request = Request(
            self.base_url + path,
            method=method,
            data=data,
            headers={"Authorization": f"Bearer {self.api_key}", **(headers or {})},
        )
        try:
            with urlopen(request, timeout=60) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read())
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get("detail", "request failed")
            except (ValueError, AttributeError):
                detail = "request failed"
            raise DzDocError(exc.code, str(detail)) from exc
