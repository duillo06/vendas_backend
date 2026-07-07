from core.exceptions.domain import DomainException


class EmptyCartError(DomainException):
    code = "EMPTY_CART"
    message = "Carrinho vazio"


class StoreClosedError(DomainException):
    code = "STORE_CLOSED"
    message = "O estabelecimento está fechado no momento"


class ProductUnavailableError(DomainException):
    code = "PRODUCT_UNAVAILABLE"
    message = "Produto indisponível"


class InvalidOptionsError(DomainException):
    code = "INVALID_OPTIONS"
    message = "Opções inválidas para o produto"


class MinOrderValueError(DomainException):
    code = "MIN_ORDER_VALUE"
    message = "Valor mínimo do pedido não atingido"


class InvalidOrderTransition(DomainException):
    code = "INVALID_ORDER_TRANSITION"

    def __init__(self, from_status: str, to_status: str):
        super().__init__(f"Transição inválida: {from_status} → {to_status}")
