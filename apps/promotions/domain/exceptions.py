from core.exceptions.domain import DomainException


class InvalidCampaignError(DomainException):
    code = "INVALID_CAMPAIGN"
    message = "Promoção inválida"
