"""Primitivas criptográficas basadas en la biblioteca estándar.

- Contraseñas: scrypt (hashlib) con sal aleatoria por usuario.
- Tokens de sesión y API keys de dispositivos: valores aleatorios cuyo
  almacenamiento se realiza como HMAC-SHA256 con la clave secreta del servidor,
  de modo que una filtración de la base de datos no permite reutilizarlos.
"""

import base64
import hashlib
import hmac
import secrets
import string

from app.core.config import get_settings

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_ALGORITHM = "scrypt"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return f"{_ALGORITHM}${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, digest_b64 = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


# Hash ficticio para igualar tiempos cuando el usuario no existe.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def verify_dummy_password(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def keyed_hash(value: str) -> str:
    key = get_settings().secret_key.encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c.isdigit() for c in candidate)
        ):
            return candidate


def generate_device_key() -> str:
    return "dk_" + secrets.token_urlsafe(32)
