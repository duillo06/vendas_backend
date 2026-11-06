"""Conversa de pedido: um passo por mensagem, cardápio de verdade."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.communications.ordering.catalog import (
    flavor_candidates,
    list_categories,
    list_products,
    load_product,
    product_public_url,
    snapshot_product,
)
from apps.communications.ordering.replies import Reply, as_buttons, as_list, brl, paged
from apps.companies.models import Company
from apps.companies.services.settings_service import SettingsService
from apps.orders.domain.enums import DeliveryType, OrderSource, PaymentMethod
from apps.orders.domain.exceptions import DomainException
from apps.orders.models import DiningTable
from apps.orders.services.cart_validation_service import CartValidationService
from apps.orders.services.order_service import OrderService
from apps.orders.services.table_service import TableService

PAY_LABELS = {
    PaymentMethod.CASH: "Dinheiro",
    PaymentMethod.PIX: "PIX",
    PaymentMethod.CARD_ON_DELIVERY: "Cartão na entrega",
}

TEXT_STEPS = {
    "address_street",
    "address_number",
    "address_neighborhood",
    "address_reference",
    "table",
    "name",
    "change",
}


def _tail_int(choice: str) -> int:
    try:
        return int(choice.rsplit(":", 1)[-1])
    except ValueError:
        return 0


def fresh_draft(push_name: str = "") -> dict:
    return {
        "items": [],
        "building": None,
        "category_id": "",
        "cat_page": 0,
        "prod_page": 0,
        "push_name": (push_name or "").strip(),
        "customer_name": "",
        "fulfillment": "",
        "address": {},
        "table_id": "",
        "table_number": "",
        "payment_method": "",
        "hint": "",
    }


def prompt(session, tenant: Company) -> Reply:
    # opções atuais, sem consumir o aviso
    return _render(session, tenant)


def render(session, tenant: Company) -> Reply:
    hint = ""
    if session.draft:
        hint = session.draft.pop("hint", "") or ""
    return _render(session, tenant).with_hint(hint)


def consume(session, tenant: Company, *, choice: str, text: str) -> None:
    step = session.step
    draft = session.draft
    if step in TEXT_STEPS and not choice:
        _consume_text(session, tenant, text)
        return
    if not choice:
        draft["hint"] = "Não entendi. Escolhe uma das opções."
        return
    handlers = {
        "menu": _on_menu,
        "products": _on_products,
        "build": _on_build,
        "more": _on_more,
        "fulfill": _on_fulfill,
        "address_reference": _on_reference,
        "name": _on_name,
        "payment": _on_payment,
        "summary": _on_summary,
    }
    handler = handlers.get(step)
    if handler is None:
        draft["hint"] = "Não entendi. Escolhe uma das opções."
        return
    handler(session, tenant, choice)


def choice_from_reply(reply: Reply, text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    folded = raw.casefold()
    options = list(reply.buttons) or [(item_id, title) for item_id, title, _desc in reply.rows]
    for item_id, label in options:
        if label.casefold() == folded:
            return item_id
    number, rest = _leading_number(raw)
    if 1 <= number <= len(options):
        label = options[number - 1][1].casefold()
        if not rest or rest.casefold() == label or rest.casefold() in label:
            return options[number - 1][0]
    if len(folded) >= 3:
        hits = [item for item in options if folded in item[1].casefold() or item[1].casefold() in folded]
        if len(hits) == 1:
            return hits[0][0]
    return ""


def _leading_number(text: str) -> tuple[int, str]:
    digits = ""
    for char in text:
        if char.isdigit():
            digits += char
        else:
            break
    if not digits:
        return 0, ""
    return int(digits), text[len(digits) :].lstrip(" .)-")


def _render(session, tenant: Company) -> Reply:
    step = session.step
    if step == "menu":
        return _categories(session, tenant)
    if step == "products":
        return _products(session, tenant)
    if step == "build":
        return _build(session, tenant)
    if step == "more":
        return as_buttons(
            "Quer mais alguma coisa?",
            [("cart:more", "Mais um item"), ("cart:close", "Fechar pedido")],
        )
    if step == "fulfill":
        return _fulfill(tenant)
    if step == "address_street":
        return Reply(body="Qual a rua?")
    if step == "address_number":
        return Reply(body="Qual o número?")
    if step == "address_neighborhood":
        return Reply(body="Qual o bairro?")
    if step == "address_reference":
        return as_buttons("Tem um ponto de referência?", [("ref:skip", "Sem referência")])
    if step == "table":
        return Reply(body="Qual o número da sua mesa?")
    if step == "name":
        return _name(session)
    if step == "payment":
        return _payment(tenant)
    if step == "change":
        return _change(session, tenant)
    if step == "summary":
        return _summary(session, tenant)
    session.step = "menu"
    return _categories(session, tenant)


def _categories(session, tenant: Company) -> Reply:
    categories = list_categories(tenant)
    if not categories:
        return Reply(body="O cardápio ainda não tem produtos disponíveis.")
    page = int(session.draft.get("cat_page") or 0)
    rows, _start = paged(
        categories,
        page,
        lambda category: (
            f"cat:{category.id}",
            category.name,
            "",
        ),
        f"page:cat:{page + 1}",
    )
    return as_list("O que você quer pedir?", rows, button_label="Ver cardápio")


def _products(session, tenant: Company) -> Reply:
    products = list_products(tenant, session.draft.get("category_id") or "")
    if not products:
        session.step = "menu"
        session.draft["hint"] = "Essa categoria está vazia."
        return _categories(session, tenant)
    page = int(session.draft.get("prod_page") or 0)
    start = max(page, 0) * 8
    chunk = products[start : start + 8]
    rows = [(f"prod:{product.id}", product.name, brl(product.base_price)) for product in chunk]
    if start + 8 < len(products):
        rows.append((f"page:prod:{page + 1}", "Ver mais", ""))
    rows.append(("back:menu", "Voltar", ""))
    return as_list("Qual produto?", rows, button_label="Ver produtos")


def _fulfill(tenant: Company) -> Reply:
    options = _fulfillment_options(tenant)
    if not options:
        return Reply(body="Essa loja não está recebendo pedidos agora.")
    if len(options) <= 3:
        return as_buttons("Como você quer receber?", options)
    rows = [(item_id, label, "") for item_id, label in options]
    return as_list("Como você quer receber?", rows)


def _name(session) -> Reply:
    push = (session.draft.get("push_name") or "").strip()
    if len(push) >= 2:
        return as_buttons(
            f"Seu nome é {push}? Se não for, digite o nome.",
            [("name:keep", push)],
        )
    return Reply(body="Qual o seu nome?")


def _payment(tenant: Company) -> Reply:
    methods = _payment_methods(tenant)
    if not methods:
        return Reply(body="A loja não tem forma de pagamento cadastrada.")
    options = [(f"pay:{key}", label) for key, label in methods]
    if len(options) <= 3:
        return as_buttons("Como vai pagar?", options)
    return as_list("Como vai pagar?", [(item_id, label, "") for item_id, label in options])


def _change(session, tenant: Company) -> Reply:
    try:
        _subtotal, total = _quote(session, tenant)
    except DomainException as exc:
        session.step = "summary"
        return Reply(body=exc.message)
    return Reply(body=f"O pedido fica {brl(total)}. Troco para quanto?")


def _summary(session, tenant: Company) -> Reply:
    try:
        lines, total = _summary_lines(session, tenant)
    except DomainException as exc:
        return as_buttons(
            exc.message,
            [("edit:cart", "Montar de novo"), ("edit:how", "Mudar recebimento")],
        )
    body = "Confere o pedido:\n\n" + "\n".join(lines) + f"\n\nTotal {brl(total)}"
    return as_buttons(
        body,
        [("ok", "Confirmar"), ("edit:how", "Mudar recebimento"), ("edit:cart", "Montar de novo")],
    )


def _build(session, tenant: Company) -> Reply:
    building = session.draft.get("building") or {}
    _settle(building)
    session.draft["building"] = building
    if building.get("option_qty_for"):
        return as_buttons("Quantos?", [("oqty:1", "1"), ("oqty:2", "2"), ("oqty:3", "3")])
    if building.get("extra_loop"):
        return as_buttons(
            "Quer mais algum?",
            [("extra:more", "Mais um"), ("extra:done", "Pode seguir")],
        )
    if building.get("half_picking"):
        return _half_list(session, tenant, building)
    if building.get("half_asking"):
        label = (building.get("composition") or {}).get("label") or "Meio a meio"
        rule = (building.get("composition") or {}).get("pricing_rule") or ""
        body = f"Quer {building['name']} inteira ou {label.lower()}?"
        if rule == "highest":
            body += " Na meia, cobramos o sabor mais caro."
        return as_buttons(body, [("half:whole", "Inteira"), ("half:mix", "Meio a meio")])
    groups = building.get("groups") or []
    index = int(building.get("group_index") or 0)
    if index >= len(groups):
        return as_buttons(
            f"Quantos {building.get('name') or 'desse'}?",
            [("qty:1", "1"), ("qty:2", "2"), ("qty:3", "3")],
        )
    return _group_prompt(tenant, building, groups[index])


def _group_prompt(tenant: Company, building: dict, group: dict) -> Reply:
    chosen = {row["option_id"] for row in (building.get("selections") or {}).get(group["id"], [])}
    options = [option for option in group["options"] if option["id"] not in chosen]
    page = int(building.get("opt_page") or 0)
    rows, _start = paged(
        options,
        page,
        lambda option: (
            f"opt:{group['id']}:{option['id']}",
            option["name"],
            f"+ {brl(option['price'])}" if Decimal(str(option["price"])) > 0 else "",
        ),
        f"page:opt:{page + 1}",
    )
    minimum = int(group.get("min") or 0)
    if minimum == 0 and page == 0:
        rows = [("skip:" + group["id"], "Sem isso", "")] + rows
    if len(rows) > 10:
        rows = rows[:10]
    body = group["name"]
    many = group.get("selection_mode") == "quantity" and len(group["options"]) > 12
    if many and building.get("slug"):
        url = product_public_url(tenant, building["slug"])
        body += f"\n\nSe preferir montar com calma: {url}"
    if len(rows) <= 3 and all(len(title) <= 20 for _item, title, _desc in rows):
        return as_buttons(body, [(item_id, title) for item_id, title, _desc in rows])
    return as_list(body, rows, button_label="Ver opções")


def _half_list(session, tenant: Company, building: dict) -> Reply:
    product = load_product(tenant, building["product_id"])
    if product is None:
        session.step = "menu"
        return _categories(session, tenant)
    chosen = set(building.get("components") or [])
    flavors = [item for item in flavor_candidates(product) if str(item.id) not in chosen]
    page = int(building.get("half_page") or 0)
    rows, _start = paged(
        flavors,
        page,
        lambda flavor: (f"flavor:{flavor.id}", flavor.name, brl(flavor.base_price)),
        f"page:half:{page + 1}",
    )
    if building.get("components") and len(rows) < 10:
        rows.append(("half:done", "Pode seguir", ""))
    return as_list("Qual o outro sabor?", rows, button_label="Ver sabores")


def _on_menu(session, tenant: Company, choice: str) -> None:
    if choice.startswith("page:cat:"):
        session.draft["cat_page"] = _tail_int(choice)
        return
    if choice.startswith("cat:"):
        session.draft["category_id"] = choice.split(":", 1)[1]
        session.draft["prod_page"] = 0
        session.step = "products"
        return
    session.draft["hint"] = "Escolhe uma categoria."


def _on_products(session, tenant: Company, choice: str) -> None:
    if choice == "back:menu":
        session.step = "menu"
        return
    if choice.startswith("page:prod:"):
        session.draft["prod_page"] = _tail_int(choice)
        return
    if choice.startswith("prod:"):
        product = load_product(tenant, choice.split(":", 1)[1])
        if product is None:
            session.draft["hint"] = "Esse produto não está disponível."
            return
        _start_product(session, product)
        return
    session.draft["hint"] = "Escolhe um produto."


def _on_more(session, _tenant: Company, choice: str) -> None:
    if choice == "cart:more":
        session.draft["category_id"] = ""
        session.draft["cat_page"] = 0
        session.step = "menu"
        return
    if choice == "cart:close":
        session.step = "fulfill"
        return
    session.draft["hint"] = "Quer mais um item ou fechamos o pedido?"


def _on_fulfill(session, tenant: Company, choice: str) -> None:
    allowed = {item_id for item_id, _label in _fulfillment_options(tenant)}
    if choice not in allowed:
        session.draft["hint"] = "Escolhe como quer receber."
        return
    kind = choice.split(":", 1)[1]
    session.draft["fulfillment"] = kind
    if kind == DeliveryType.DELIVERY:
        session.step = "address_street"
        return
    if kind == DeliveryType.DINE_IN:
        session.step = "table"
        return
    session.step = "name"


def _on_reference(session, _tenant: Company, choice: str) -> None:
    if choice == "ref:skip":
        session.draft["address"]["reference"] = ""
        session.step = "name"
        return
    session.draft["hint"] = "Toque em sem referência ou escreva o ponto."


def _on_name(session, _tenant: Company, choice: str) -> None:
    if choice == "name:keep":
        session.draft["customer_name"] = session.draft.get("push_name") or ""
        _after_name(session)
        return
    session.draft["hint"] = "Digite seu nome."


def _on_payment(session, tenant: Company, choice: str) -> None:
    key = choice.split(":", 1)[1] if choice.startswith("pay:") else ""
    allowed = {method for method, _label in _payment_methods(tenant)}
    if key not in allowed:
        session.draft["hint"] = "Escolhe a forma de pagamento."
        return
    session.draft["payment_method"] = key
    if key == PaymentMethod.CASH:
        session.step = "change"
        return
    session.step = "summary"


def _on_summary(session, _tenant: Company, choice: str) -> None:
    if choice == "edit:cart":
        session.draft["items"] = []
        session.draft["building"] = None
        session.step = "menu"
        return
    if choice == "edit:how":
        session.step = "fulfill"
        return
    if choice == "ok":
        session.draft["confirm"] = True
        return
    session.draft["hint"] = "Confirma o pedido ou escolha o que mudar."


def _on_build(session, tenant: Company, choice: str) -> None:
    building = session.draft.get("building") or {}
    _settle(building)
    if choice.startswith("page:opt:"):
        building["opt_page"] = _tail_int(choice)
        session.draft["building"] = building
        return
    if choice.startswith("page:half:"):
        building["half_page"] = _tail_int(choice)
        session.draft["building"] = building
        return
    if building.get("option_qty_for") and choice.startswith("oqty:"):
        _store_option(building, building["option_qty_for"], _tail_int(choice) or 1)
        building["option_qty_for"] = ""
        session.draft["building"] = building
        _after_option(building)
        return
    if building.get("extra_loop"):
        if choice == "extra:more":
            building["extra_loop"] = False
            building["opt_page"] = 0
            session.draft["building"] = building
            return
        if choice == "extra:done":
            group = _current_group(building)
            count = _picked_count(building, group["id"]) if group else 0
            minimum = int(group.get("min") or 0) if group else 0
            if count < minimum:
                session.draft["hint"] = f"Escolhe pelo menos {minimum}."
                return
            building["extra_loop"] = False
            building["group_index"] = int(building.get("group_index") or 0) + 1
            building["opt_page"] = 0
            _settle(building)
            session.draft["building"] = building
            return
    if building.get("half_picking"):
        _on_half_pick(session, tenant, building, choice)
        return
    if building.get("half_asking"):
        if choice == "half:whole":
            building["half_done"] = True
            building["half_asking"] = False
            _settle(building)
            session.draft["building"] = building
            return
        if choice == "half:mix":
            building["half_asking"] = False
            building["half_picking"] = True
            building["half_page"] = 0
            session.draft["building"] = building
            return
    group = _current_group(building)
    if group and choice == f"skip:{group['id']}":
        if int(group.get("min") or 0) > 0:
            session.draft["hint"] = "Essa escolha é obrigatória."
            return
        building["group_index"] = int(building.get("group_index") or 0) + 1
        building["opt_page"] = 0
        _settle(building)
        session.draft["building"] = building
        return
    if group and choice.startswith(f"opt:{group['id']}:"):
        option_id = choice.split(":")[-1]
        if group.get("selection_mode") == "quantity":
            building["option_qty_for"] = option_id
            session.draft["building"] = building
            return
        if not _store_option(building, option_id, 1):
            session.draft["hint"] = "Essa opção não está disponível."
            session.draft["building"] = building
            return
        _after_option(building)
        session.draft["building"] = building
        return
    if choice.startswith("qty:"):
        if _current_group(building) is not None or building.get("half_asking") or building.get("half_picking"):
            session.draft["hint"] = "Falta escolher uma opção."
            return
        _finish_item(session, _tail_int(choice) or 1)
        return
    session.draft["hint"] = "Escolhe uma das opções."
    session.draft["building"] = building


def _on_half_pick(session, tenant: Company, building: dict, choice: str) -> None:
    if choice == "half:done":
        if not building.get("components"):
            session.draft["hint"] = "Escolhe o outro sabor."
            return
        building["half_picking"] = False
        building["half_done"] = True
        _settle(building)
        session.draft["building"] = building
        return
    if not choice.startswith("flavor:"):
        session.draft["hint"] = "Escolhe o outro sabor."
        return
    flavor_id = choice.split(":", 1)[1]
    product = load_product(tenant, building["product_id"])
    allowed = {str(item.id) for item in flavor_candidates(product)} if product else set()
    if flavor_id not in allowed:
        session.draft["hint"] = "Esse sabor não entra nessa pizza."
        return
    components = list(building.get("components") or [])
    if flavor_id not in components:
        components.append(flavor_id)
    building["components"] = components
    if len(components) >= _max_extra_flavors(building):
        building["half_picking"] = False
        building["half_done"] = True
        _settle(building)
    session.draft["building"] = building


def _consume_text(session, tenant: Company, text: str) -> None:
    raw = (text or "").strip()
    step = session.step
    if step == "name" and raw.casefold() in {"sim", "isso"} and session.draft.get("push_name"):
        session.draft["customer_name"] = session.draft["push_name"]
        _after_name(session)
        return
    if len(raw) < 1:
        session.draft["hint"] = "Manda a resposta em texto."
        return
    if step == "address_street":
        session.draft["address"]["street"] = raw[:255]
        session.step = "address_number"
        return
    if step == "address_number":
        session.draft["address"]["number"] = raw[:20]
        session.step = "address_neighborhood"
        return
    if step == "address_neighborhood":
        session.draft["address"]["neighborhood"] = raw[:100]
        session.step = "address_reference"
        return
    if step == "address_reference":
        session.draft["address"]["reference"] = raw[:255]
        session.step = "name"
        return
    if step == "table":
        _apply_table(session, tenant, raw)
        return
    if step == "name":
        if len(raw) < 2:
            session.draft["hint"] = "O nome precisa ter pelo menos 2 letras."
            return
        session.draft["customer_name"] = raw[:200]
        _after_name(session)
        return
    if step == "change":
        _apply_change(session, tenant, raw)
        return
    if step == "build" and raw.isdigit():
        _on_build(session, tenant, f"qty:{int(raw)}")
        return


def _apply_table(session, tenant: Company, number: str) -> None:
    try:
        table = TableService.resolve_by_number(tenant=tenant, number=number)
    except DomainException:
        session.draft["hint"] = "Não encontramos essa mesa. Confere o número."
        return
    session.draft["table_id"] = str(table.id)
    session.draft["table_number"] = table.number
    session.draft["payment_method"] = PaymentMethod.PAY_AT_VENUE
    name = session.draft.get("push_name") or f"Mesa {table.number}"
    session.draft["customer_name"] = name
    session.step = "summary"


def _apply_change(session, tenant: Company, raw: str) -> None:
    cleaned = raw.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        session.draft["hint"] = "Manda o valor, por exemplo 50."
        return
    try:
        _subtotal, total = _quote(session, tenant)
    except DomainException as exc:
        session.draft["hint"] = exc.message
        return
    if amount <= total:
        session.draft["hint"] = f"O troco precisa ser maior que {brl(total)}."
        return
    session.draft["change_for"] = str(amount.quantize(Decimal("0.01")))
    session.step = "summary"


def _after_name(session) -> None:
    if session.draft.get("fulfillment") == DeliveryType.DINE_IN:
        session.step = "summary"
        return
    session.step = "payment"


def _start_product(session, product) -> None:
    snap = snapshot_product(product)
    building = {
        "product_id": snap["product_id"],
        "name": snap["name"],
        "slug": snap["slug"],
        "groups": snap["groups"],
        "composition": snap["composition"],
        "group_index": 0,
        "selections": {},
        "components": [],
        "half_done": snap["composition"] is None,
        "half_asking": False,
        "half_picking": False,
        "half_page": 0,
        "extra_loop": False,
        "option_qty_for": "",
        "opt_page": 0,
    }
    _settle(building)
    session.draft["building"] = building
    session.step = "build"


def _finish_item(session, quantity: int) -> None:
    building = session.draft["building"]
    quantity = min(99, max(1, quantity))
    options = []
    for rows in (building.get("selections") or {}).values():
        options.extend(rows)
    session.draft["items"].append(
        {
            "product_id": building["product_id"],
            "quantity": quantity,
            "options": options,
            "components": list(building.get("components") or []),
        }
    )
    session.draft["building"] = None
    session.step = "more"


def _store_option(building: dict, option_id: str, quantity: int) -> bool:
    group = _current_group(building)
    if group is None:
        return False
    known = {option["id"] for option in group["options"]}
    if option_id not in known:
        return False
    rows = list((building.get("selections") or {}).get(group["id"], []))
    if group["selection_type"] == "single":
        rows = [{"option_id": option_id, "quantity": quantity}]
    else:
        rows = [row for row in rows if row["option_id"] != option_id]
        rows.append({"option_id": option_id, "quantity": quantity})
    building.setdefault("selections", {})[group["id"]] = rows
    return True


def _after_option(building: dict) -> None:
    group = _current_group(building)
    if group is None:
        return
    if group["selection_type"] == "single":
        building["group_index"] = int(building.get("group_index") or 0) + 1
        building["opt_page"] = 0
        building["extra_loop"] = False
        _settle(building)
        return
    count = _picked_count(building, group["id"])
    limit = _group_max(group)
    if count >= limit:
        building["group_index"] = int(building.get("group_index") or 0) + 1
        building["opt_page"] = 0
        building["extra_loop"] = False
        _settle(building)
        return
    building["extra_loop"] = True


def _settle(building: dict) -> None:
    if building.get("option_qty_for") or building.get("extra_loop") or building.get("half_picking"):
        building["half_asking"] = False
        return
    building["half_asking"] = False
    while True:
        if _need_half(building):
            building["half_asking"] = True
            return
        groups = building.get("groups") or []
        index = int(building.get("group_index") or 0)
        if index >= len(groups):
            return
        if groups[index]["options"]:
            return
        building["group_index"] = index + 1


def _need_half(building: dict) -> bool:
    if building.get("half_done") or not building.get("composition"):
        return False
    groups = building.get("groups") or []
    index = int(building.get("group_index") or 0)
    size_at = [pos for pos, group in enumerate(groups) if group.get("kind") in {"size", "volume"}]
    if not size_at:
        return index == 0
    return index > max(size_at)


def _current_group(building: dict) -> dict | None:
    groups = building.get("groups") or []
    index = int(building.get("group_index") or 0)
    if index >= len(groups):
        return None
    group = groups[index]
    if not group["options"]:
        return None
    return group


def _picked_count(building: dict, group_id: str) -> int:
    return sum(int(row.get("quantity") or 1) for row in (building.get("selections") or {}).get(group_id, []))


def _group_max(group: dict) -> int:
    raw = int(group.get("max") or 0)
    if raw <= 0:
        return 10
    return raw


def _max_extra_flavors(building: dict) -> int:
    composition = building.get("composition") or {}
    max_parts = int(composition.get("max_parts") or 2)
    size_id = _selected_size_id(building)
    by_size = composition.get("max_parts_by_size") or {}
    if size_id and str(size_id) in by_size:
        max_parts = int(by_size[str(size_id)])
    return max(1, max_parts - 1)


def _selected_size_id(building: dict) -> str:
    for group in building.get("groups") or []:
        if group.get("kind") not in {"size", "volume"}:
            continue
        rows = (building.get("selections") or {}).get(group["id"]) or []
        if rows:
            return rows[0]["option_id"]
    return ""


def _fulfillment_options(tenant: Company) -> list[tuple[str, str]]:
    settings = SettingsService.get_for_tenant(tenant)
    options = []
    if settings.accepts_delivery:
        options.append(("how:delivery", "Entrega"))
    if settings.accepts_pickup:
        options.append(("how:pickup", "Retirada"))
    has_table = DiningTable.all_objects.filter(tenant=tenant, is_active=True).exists()
    if settings.accepts_dine_in and has_table:
        options.append(("how:dine_in", "Estou na loja"))
    return options


def _payment_methods(tenant: Company) -> list[tuple[str, str]]:
    settings = SettingsService.get_for_tenant(tenant)
    methods = []
    for key in settings.payment_methods or []:
        if key in PAY_LABELS:
            methods.append((key, PAY_LABELS[key]))
    return methods


def checkout_items(draft: dict) -> list[dict]:
    return [
        {
            "product_id": item["product_id"],
            "quantity": item["quantity"],
            "options": item.get("options") or [],
            "components": item.get("components") or [],
            "notes": "",
        }
        for item in draft.get("items") or []
    ]


def checkout_data(session, phone: str) -> dict:
    draft = session.draft
    fulfillment = draft.get("fulfillment") or DeliveryType.PICKUP
    data = {
        "customer_name": (draft.get("customer_name") or "Cliente").strip(),
        "customer_phone": phone,
        "delivery_type": fulfillment,
        "payment_method": draft.get("payment_method") or PaymentMethod.PIX,
        "items": checkout_items(draft),
        "notes": "",
    }
    if fulfillment == DeliveryType.DELIVERY:
        data["address"] = _address_payload(session)
    if fulfillment == DeliveryType.DINE_IN:
        data["table_id"] = draft.get("table_id")
        data["payment_method"] = PaymentMethod.PAY_AT_VENUE
    if draft.get("payment_method") == PaymentMethod.CASH and draft.get("change_for"):
        data["change_for"] = draft["change_for"]
    return data


def _address_payload(session) -> dict:
    tenant = session.tenant
    settings = SettingsService.get_for_tenant(tenant)
    address = dict(session.draft.get("address") or {})
    address.setdefault("street", "")
    address.setdefault("number", "")
    address.setdefault("neighborhood", "")
    address.setdefault("complement", "")
    address.setdefault("reference", "")
    address["city"] = settings.delivery_city or address.get("city") or ""
    address["state"] = settings.delivery_state or address.get("state") or ""
    if settings.delivery_city_ref_id:
        address["city_id"] = settings.delivery_city_ref_id
        address["state_id"] = settings.delivery_city_ref.state_id
    return address


def _quote(session, tenant: Company) -> tuple[Decimal, Decimal]:
    validated = CartValidationService.validate(tenant=tenant, items=checkout_items(session.draft))
    subtotal = sum((item["total_price"] for item in validated), Decimal("0"))
    fee = OrderService._calculate_delivery_fee(
        tenant=tenant,
        delivery_type=session.draft.get("fulfillment") or DeliveryType.PICKUP,
        subtotal=subtotal,
    )
    return subtotal, subtotal + fee


def _summary_lines(session, tenant: Company) -> tuple[list[str], Decimal]:
    validated = CartValidationService.validate(tenant=tenant, items=checkout_items(session.draft))
    lines = []
    for item in validated:
        lines.append(f"{item['quantity']}× {item['product_name']} — {brl(item['total_price'])}")
        for option in item["options"]:
            extra = ""
            if option["price_modifier"]:
                extra = f" (+ {brl(option['price_modifier'])})"
            lines.append(f"· {option['name']}{extra}")
        for part in item["components"]:
            lines.append(f"· Meia {part['product_name']}")
    subtotal = sum((item["total_price"] for item in validated), Decimal("0"))
    fee = OrderService._calculate_delivery_fee(
        tenant=tenant,
        delivery_type=session.draft.get("fulfillment") or DeliveryType.PICKUP,
        subtotal=subtotal,
    )
    if fee:
        lines.append(f"Entrega {brl(fee)}")
    how = {
        DeliveryType.DELIVERY: "Entrega",
        DeliveryType.PICKUP: "Retirada",
        DeliveryType.DINE_IN: f"Mesa {session.draft.get('table_number') or ''}".strip(),
    }.get(session.draft.get("fulfillment"), "")
    if how:
        lines.insert(0, how)
    return lines, subtotal + fee


def place_order(session, phone: str):
    return OrderService.create_from_checkout(
        tenant=session.tenant,
        data=checkout_data(session, phone),
        source=OrderSource.WHATSAPP,
    )


def touch_expiry(session) -> None:
    session.expires_at = timezone.now() + timezone.timedelta(minutes=30)
