"""Política de contraseñas."""

from app.core.errors import BusinessRuleError

MIN_LENGTH = 10
MAX_LENGTH = 128


def validate_password_policy(password: str, *, username: str) -> None:
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append(f"debe tener al menos {MIN_LENGTH} caracteres")
    if len(password) > MAX_LENGTH:
        problems.append(f"no debe superar {MAX_LENGTH} caracteres")
    if not any(c.isalpha() for c in password):
        problems.append("debe incluir al menos una letra")
    if not any(c.isdigit() for c in password):
        problems.append("debe incluir al menos un número")
    if username and username.lower() in password.lower():
        problems.append("no debe contener el nombre de usuario")
    if problems:
        raise BusinessRuleError(
            "La contraseña no cumple la política de seguridad: " + "; ".join(problems) + ".",
            code="contrasena_debil",
            details=problems,
        )
