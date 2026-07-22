from apps.communications.infrastructure.providers._fake.adapter import FakeWhatsAppAdapter
from apps.communications.infrastructure.providers.evolution.adapter import EvolutionWhatsAppAdapter

_REGISTRY: dict[str, object] = {}


def get_provider(provider_key: str):
    if provider_key not in _REGISTRY:
        if provider_key == "evolution":
            _REGISTRY[provider_key] = EvolutionWhatsAppAdapter()
        elif provider_key == "fake":
            _REGISTRY[provider_key] = FakeWhatsAppAdapter()
        else:
            raise KeyError(f"Provedor não registrado: {provider_key}")
    return _REGISTRY[provider_key]


def register_provider(provider_key: str, adapter) -> None:
    _REGISTRY[provider_key] = adapter
