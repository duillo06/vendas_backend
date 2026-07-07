from core.exceptions.domain import DomainException


class InvalidOptionSelection(DomainException):
    code = "INVALID_OPTION_SELECTION"


class CategoryHasActiveProducts(DomainException):
    code = "CATEGORY_HAS_PRODUCTS"
    message = "Categoria com produtos ativos não pode ser removida"


class ImageLimitExceeded(DomainException):
    code = "IMAGE_LIMIT_EXCEEDED"
    message = "Máximo de 5 imagens por produto"
