"""credenciais assinadas com SECRET_KEY — não logar o valor"""

from django.core import signing

SALT = "communications.connection.credentials"


def seal_credentials(data: dict) -> str:
    return signing.dumps(data, salt=SALT, compress=True)


def open_credentials(signed: str) -> dict:
    if not signed:
        return {}
    return signing.loads(signed, salt=SALT)
