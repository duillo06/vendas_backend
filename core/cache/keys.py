def tenant_key(tenant_id: str, *parts: str) -> str:
    return f"tenant:{tenant_id}:{':'.join(parts)}"
