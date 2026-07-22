import logging
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "FoodService/1.0 (vendas; contact@localhost)"
TIMEOUT_SECONDS = 5

# siglas BR a partir do ISO3166-2-lvl4 (ex.: BR-SP)
_UF_FROM_ISO = re.compile(r"^BR-([A-Z]{2})$", re.IGNORECASE)

# fallback nome → UF quando Nominatim não manda ISO
_STATE_NAME_TO_UF = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}


def normalize_city(value: str) -> str:
    """compara cidade sem acento / case"""
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


def normalize_state(value: str) -> str:
    return (value or "").strip().upper()[:2]


def cities_match(a: str, b: str) -> bool:
    return normalize_city(a) == normalize_city(b) and bool(normalize_city(a))


def _uf_from_address(addr: dict) -> str:
    iso = (addr.get("ISO3166-2-lvl4") or "").strip()
    match = _UF_FROM_ISO.match(iso)
    if match:
        return match.group(1).upper()

    raw = (addr.get("state") or "").strip()
    if len(raw) == 2:
        return raw.upper()

    return _STATE_NAME_TO_UF.get(normalize_city(raw), "")


def _city_from_address(addr: dict) -> str:
    for key in ("city", "town", "village", "municipality", "suburb", "county"):
        value = (addr.get(key) or "").strip()
        if value:
            return value
    return ""


class GeoService:
    @staticmethod
    def reverse(*, lat: float, lng: float) -> dict[str, str]:
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            raise ValidationError({"detail": "Coordenadas inválidas"})

        query = urlencode(
            {
                "lat": f"{lat:.7f}",
                "lon": f"{lng:.7f}",
                "format": "json",
                "addressdetails": 1,
                "zoom": 14,
            }
        )
        request = Request(
            f"{NOMINATIM_URL}?{query}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                import json

                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            logger.warning("reverse geocode failed: %s", exc)
            raise ValidationError(
                {"detail": "Não foi possível descobrir a cidade pela localização"}
            ) from exc

        addr = payload.get("address") or {}
        city = _city_from_address(addr)
        state = _uf_from_address(addr)

        if not city or not state:
            raise ValidationError(
                {"detail": "Não encontramos cidade e estado para essa localização"}
            )

        return {"city": city, "state": state}
