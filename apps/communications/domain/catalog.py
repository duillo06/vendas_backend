"""catálogo de situações + seeds — o comerciante vê títulos, não event_key"""

from apps.communications.domain.enums import PHASE1_EVENT_KEYS

# chip UI → chave no payload do evento
UI_TOKEN_TO_PAYLOAD = {
    "cliente": "customer_name",
    "pedido": "order_number",
    "valor": "total_formatted",
    "tempo": "eta_text",
    "restaurante": "company_name",
    "endereco": "delivery_address",
    "pagamento": "payment_method_label",
}

PREVIEW_SAMPLES = {
    "customer_name": "Maria",
    "order_number": "#1042",
    "total_formatted": "R$ 89,90",
    "eta_text": "40–50 minutos",
    "company_name": "Seu Restaurante",
    "delivery_address": "Rua das Flores, 100",
    "payment_method_label": "PIX",
}

SITUATION_CATALOG: dict[str, dict] = {
    "order.received": {
        "title": "Pedido recebido",
        "description": "Avisamos o cliente quando o pedido chega na loja.",
        "variables": ["cliente", "pedido", "valor", "restaurante"],
        "seed": (
            "Olá {{cliente}}!\n\n"
            "Recebemos seu pedido {{pedido}}.\n"
            "Valor: {{valor}}\n\n"
            "Em breve confirmamos por aqui 😊\n"
            "{{restaurante}}"
        ),
    },
    "order.confirmed": {
        "title": "Pedido confirmado",
        "description": "Quando você confirma o pedido.",
        "variables": ["cliente", "pedido", "valor", "tempo", "restaurante"],
        "seed": (
            "Olá {{cliente}}!\n\n"
            "Recebemos seu pedido!\n\n"
            "Pedido: {{pedido}}\n"
            "Valor: {{valor}}\n"
            "Tempo estimado: {{tempo}}\n\n"
            "Obrigado ❤️\n"
            "{{restaurante}}"
        ),
    },
    "order.preparing": {
        "title": "Pedido em preparo",
        "description": "Quando a cozinha começa a preparar.",
        "variables": ["cliente", "pedido", "tempo", "restaurante"],
        "seed": (
            "Olá {{cliente}}!\n\n"
            "Seu pedido {{pedido}} já está em preparo.\n"
            "Tempo estimado: {{tempo}}\n\n"
            "{{restaurante}}"
        ),
    },
    "order.out_for_delivery": {
        "title": "Pedido saiu para entrega",
        "description": "Quando o pedido sai para entrega.",
        "variables": ["cliente", "pedido", "tempo", "restaurante"],
        "seed": (
            "Olá {{cliente}}!\n\n"
            "Seu pedido {{pedido}} saiu para entrega!\n"
            "Chega em breve 🛵\n\n"
            "{{restaurante}}"
        ),
    },
    "order.delivered": {
        "title": "Pedido entregue",
        "description": "Quando o pedido é concluído / entregue.",
        "variables": ["cliente", "pedido", "restaurante"],
        "seed": (
            "Olá {{cliente}}!\n\n"
            "Pedido {{pedido}} entregue! Bom apetite 🍽️\n\n"
            "Obrigado pela preferência!\n"
            "{{restaurante}}"
        ),
    },
    "payment.approved": {
        "title": "Pagamento aprovado",
        "description": "Quando o pagamento é confirmado.",
        "variables": ["cliente", "pedido", "valor", "restaurante"],
        "seed": (
            "Olá {{cliente}}!\n\n"
            "Pagamento do pedido {{pedido}} confirmado.\n"
            "Valor: {{valor}}\n\n"
            "{{restaurante}}"
        ),
    },
    "payment.rejected": {
        "title": "Pagamento recusado",
        "description": "Quando o pagamento falha.",
        "variables": ["cliente", "pedido", "valor", "restaurante"],
        "seed": (
            "Olá {{cliente}}!\n\n"
            "Não conseguimos confirmar o pagamento do pedido {{pedido}} "
            "({{valor}}).\n"
            "Se precisar, fale conosco.\n\n"
            "{{restaurante}}"
        ),
    },
}

assert set(SITUATION_CATALOG) == set(PHASE1_EVENT_KEYS)

# error_code do adapter → copy humana (25 §7) — sem jargão técnico
ERROR_COPY = {
    "credentials_invalid": "Não conseguimos acessar com essa chave. Confira e tente de novo.",
    "server_unreachable": "Não encontramos o servidor nesse endereço.",
    "provider_timeout": (
        "O WhatsApp demorou para responder. Feche o WhatsApp Web no computador "
        "e tente de novo — ou reconecte."
    ),
    "session_disconnected": "Seu WhatsApp foi desconectado.",
    "session_unstable": (
        "Esse WhatsApp está em conflito com outro aparelho. "
        "Feche o WhatsApp Web e reconecte."
    ),
    "qr_expired": "Este QR Code expirou. Vamos gerar outro?",
    "send_failed": (
        "Não conseguimos enviar a mensagem. Se o WhatsApp Web estiver aberto, "
        "feche e reconecte."
    ),
    "rate_limited": "Muitas tentativas. Aguarde um momento.",
    "unknown": "Algo deu errado. Tente de novo.",
}

# conflito típico: mesmo número no Web + no sistema
SESSION_UNSTABLE_TITLE = "WhatsApp em conflito com outro aparelho"
SESSION_UNSTABLE_BODY = (
    "Esse número parece estar aberto no WhatsApp Web ou em outro celular "
    "ao mesmo tempo. Enquanto isso, as mensagens automáticas podem falhar "
    "mesmo com status “conectado”.\n\n"
    "Para resolver:\n"
    "1. No celular, abra WhatsApp → Aparelhos conectados\n"
    "2. Desconecte os outros aparelhos (WhatsApp Web, computador, etc.)\n"
    "3. Volte aqui e toque em Reconectar WhatsApp\n"
    "4. Escaneie o QR Code só uma vez — e não abra o WhatsApp Web depois"
)
SESSION_UNSTABLE_ACTION = "Reconectar WhatsApp"


def human_error(error_code: str | None) -> str:
    return ERROR_COPY.get(error_code or "unknown", ERROR_COPY["unknown"])
