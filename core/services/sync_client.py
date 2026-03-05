import json
from typing import Dict, Optional
from urllib import request


class SyncClient:
    def __init__(self, server_url: str, api_key: Optional[str] = None):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key

    def _post(self, path: str, payload: Dict) -> Dict:
        req = request.Request(
            f"{self.server_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        with request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def ping(self, payload: Dict) -> Dict:
        return self._post("/ping", payload)

    def push_events(self, payload: Dict) -> Dict:
        return self._post("/push", payload)

    def get_catalog_items(self, payload: Dict) -> Dict:
        return self._post("/catalog/items", payload)

    def get_catalog_categories(self, payload: Dict) -> Dict:
        return self._post("/catalog/categories", payload)
