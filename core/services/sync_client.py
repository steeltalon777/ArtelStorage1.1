import json
import time
from typing import Dict, Optional
from urllib import error, request


class SyncHttpError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        body: Optional[dict] = None,
        retry_after: Optional[int] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body or {}
        self.retry_after = retry_after
        self.request_id = request_id


class SyncClient:
    def __init__(self, server_url: str, device_token: Optional[str] = None, client_version: Optional[str] = None):
        self.server_url = server_url.rstrip("/")
        self.device_token = (device_token or "").strip()
        self.client_version = (client_version or "").strip()

    def _build_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.device_token:
            headers["X-Device-Token"] = self.device_token
        if self.client_version:
            headers["X-Client-Version"] = self.client_version
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _post(self, path: str, payload: Dict, extra_headers: Optional[Dict[str, str]] = None) -> Dict:
        started = time.time()
        req = request.Request(
            f"{self.server_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._build_headers(extra_headers),
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                body = json.loads(raw) if raw else {}
                request_id = resp.headers.get("X-Request-Id") or body.get("request_id")
                body["_meta"] = {
                    "endpoint": path,
                    "status_code": int(getattr(resp, "status", 200)),
                    "latency_ms": int((time.time() - started) * 1000),
                    "request_id": request_id,
                }
                return body
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp else ""
            parsed = {}
            if raw:
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = {"error": raw}
            request_id = exc.headers.get("X-Request-Id") if exc.headers else None
            retry_after_header = exc.headers.get("Retry-After") if exc.headers else None
            retry_after = int(retry_after_header) if retry_after_header and retry_after_header.isdigit() else None
            raise SyncHttpError(
                status_code=int(exc.code),
                message=f"HTTP {exc.code} on {path}",
                body=parsed,
                retry_after=retry_after,
                request_id=request_id or parsed.get("request_id"),
            ) from exc
        except error.URLError as exc:
            raise SyncHttpError(status_code=0, message=f"Network error on {path}: {exc.reason}") from exc

    def ping(self, payload: Dict) -> Dict:
        return self._post("/ping", payload)

    def push_events(self, payload: Dict) -> Dict:
        return self._post("/push", payload)

    def pull_events(self, payload: Dict) -> Dict:
        return self._post("/pull", payload)

    def get_catalog_items(self, payload: Dict) -> Dict:
        return self._post(
            "/catalog/items",
            payload,
            extra_headers={
                "X-Site-Id": str(payload.get("site_id") or ""),
                "X-Device-Id": str(payload.get("device_id") or ""),
            },
        )

    def get_catalog_categories(self, payload: Dict) -> Dict:
        return self._post(
            "/catalog/categories",
            payload,
            extra_headers={
                "X-Site-Id": str(payload.get("site_id") or ""),
                "X-Device-Id": str(payload.get("device_id") or ""),
            },
        )
