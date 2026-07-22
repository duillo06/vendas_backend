from core.exceptions.domain import DomainException


class CommunicationError(DomainException):
    code = "COMMUNICATION_ERROR"
    message = "Não foi possível concluir a comunicação"


class ConnectionError(CommunicationError):
    code = "CONNECTION_ERROR"
    message = "Não foi possível conectar"


class ProviderError(CommunicationError):
    """erro do vendor — error_code alimenta copy humana"""

    code = "PROVIDER_ERROR"
    message = "Algo deu errado na conexão"

    def __init__(self, error_code: str, message: str | None = None):
        self.error_code = error_code
        super().__init__(message or self.message)


class TemplateValidationError(CommunicationError):
    code = "TEMPLATE_INVALID"
    message = "Mensagem inválida"
