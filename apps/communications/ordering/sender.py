import logging

from apps.communications.domain.ports import ConnectionContext
from apps.communications.infrastructure.providers.evolution.client import EvolutionHttpError
from apps.communications.ordering.replies import Reply

logger = logging.getLogger(__name__)


def send_replies(provider, ctx: ConnectionContext, phone: str, replies: list[Reply]) -> None:
    for reply in replies:
        _send_one(provider, ctx, phone, reply)


def _send_one(provider, ctx: ConnectionContext, phone: str, reply: Reply) -> None:
    # lista e botão dessa Evolution não aparecem no celular — manda numerado
    try:
        provider.send_text(ctx, to_e164=phone, body=_as_text(reply))
    except EvolutionHttpError:
        logger.info("texto do pedido não saiu")
    except Exception:
        logger.exception("falha ao responder no WhatsApp")


def _as_text(reply: Reply) -> str:
    lines = [reply.body]
    if reply.buttons:
        options = [label for _item, label in reply.buttons]
    else:
        options = [f"{title} — {desc}" if desc else title for _item, title, desc in reply.rows]
    if options:
        lines.append("")
        lines.extend(f"{index}. {label}" for index, label in enumerate(options, start=1))
    return "\n".join(lines)
