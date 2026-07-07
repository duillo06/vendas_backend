class DomainException(Exception):
    code: str = "DOMAIN_ERROR"
    message: str = "Erro de domínio"

    def __init__(self, message: str | None = None):
        self.message = message or self.__class__.message
        super().__init__(self.message)
