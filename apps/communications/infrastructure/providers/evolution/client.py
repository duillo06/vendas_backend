import json
import logging
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class EvolutionHttpError(Exception):
    def __init__(self, error_code: str, status: int | None = None, detail: Any = None):
        self.error_code = error_code
        self.status = status
        self.detail = detail
        super().__init__(error_code)


class EvolutionHttpClient:
    """HTTP fino pra Evolution — só este pacote conhece os paths"""

    def __init__(self, base_url: str, api_key: str, timeout: float = 25.0):
        self.base_url = base_url.rstrip("/") + "/"
        self.api_key = api_key
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
    ) -> tuple[int, Any]:
        url = urljoin(self.base_url, path.lstrip("/"))
        data = None
        headers = {
            "apikey": self.api_key,
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8") or "{}"
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = {"raw": raw}
                return resp.status, parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"raw": raw}
            return exc.code, parsed
        except TimeoutError as exc:
            raise EvolutionHttpError("provider_timeout") from exc
        except urllib.error.URLError as exc:
            logger.info("Evolution inacessível: %s", type(exc.reason).__name__)
            raise EvolutionHttpError("server_unreachable") from exc
