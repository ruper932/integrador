"""Comandos de administración local.

Uso:
    python -m app.cli create-admin --username admin --full-name "Administrador"
    python -m app.cli ensure-admin --username admin

`create-admin` solicita la contraseña por consola (no se acepta como argumento para
que no quede en el historial de la terminal). `ensure-admin` crea el administrador
solo si no existe ninguno activo, con una contraseña temporal que se muestra una vez
y que debe cambiarse en el primer inicio de sesión.
"""

import argparse
import getpass
import sys

from app.business.rules.passwords import validate_password_policy
from app.core.errors import AppError
from app.core.permissions import ROLE_ADMIN
from app.core.security import generate_temporary_password, hash_password
from app.data.database import SessionLocal
from app.data.models.people import UserProfile
from app.data.models.security import AuditLog, User
from app.data.repositories.security import RoleRepository, UserRepository


def create_admin(username: str, full_name: str) -> int:
    with SessionLocal() as session:
        users = UserRepository(session)
        if users.get_by_username(username):
            print(f"Ya existe el usuario '{username}'.", file=sys.stderr)
            return 1
        role = RoleRepository(session).get_by_name(ROLE_ADMIN)
        if role is None:
            print("No existe el rol administrador. Ejecute primero: alembic upgrade head", file=sys.stderr)
            return 1
        password = getpass.getpass("Contraseña: ")
        if password != getpass.getpass("Repita la contraseña: "):
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 1
        try:
            validate_password_policy(password, username=username)
        except AppError as exc:
            print(exc.message, file=sys.stderr)
            return 1
        user = users.add(
            User(
                username=username,
                # El perfil queda incompleto (sin CI ni celular) hasta completarlo desde el panel.
                profile=UserProfile(first_names=full_name),
                password_hash=hash_password(password),
                is_active=True,
                must_change_password=False,
                failed_login_attempts=0,
                roles=[role],
            )
        )
        session.add(
            AuditLog(user_id=None, action="usuario.crear_admin_cli", entity_type="user", entity_id=str(user.id))
        )
        session.commit()
        print(f"Administrador '{username}' creado.")
        return 0


def ensure_admin(username: str, full_name: str) -> int:
    with SessionLocal() as session:
        role = RoleRepository(session).get_by_name(ROLE_ADMIN)
        if role is None:
            print("No existe el rol administrador. Ejecute primero: alembic upgrade head", file=sys.stderr)
            return 1
        users = UserRepository(session)
        admins = [u for u in users.list(limit=10_000, is_active=True) if any(r.name == ROLE_ADMIN for r in u.roles)]
        if admins:
            print(f"Ya existe un administrador activo: {', '.join(u.username for u in admins)}.")
            return 0
        if users.get_by_username(username):
            print(f"El usuario '{username}' existe pero no es administrador activo.", file=sys.stderr)
            return 1
        temporary = generate_temporary_password()
        user = users.add(
            User(
                username=username,
                profile=UserProfile(first_names=full_name),
                password_hash=hash_password(temporary),
                is_active=True,
                must_change_password=True,
                failed_login_attempts=0,
                roles=[role],
            )
        )
        session.add(
            AuditLog(user_id=None, action="usuario.crear_admin_cli", entity_type="user", entity_id=str(user.id))
        )
        session.commit()
        print(f"Administrador creado. Usuario: {username}  Contraseña temporal: {temporary}")
        print("Guárdela ahora: no se volverá a mostrar y deberá cambiarse en el primer inicio de sesión.")
        return 0


def seed_demo() -> int:
    from app.core.config import get_settings
    from app.demo_data import DEMO_PASSWORD, USERS, DemoSeeder, SeedError

    if get_settings().environment == "production":
        print("Los datos de demostración no se cargan en producción.", file=sys.stderr)
        return 1
    with SessionLocal() as session:
        try:
            result = DemoSeeder(session).run()
        except SeedError as exc:
            print(exc, file=sys.stderr)
            return 1
    print(f"Datos de demostración cargados: {result['usuarios']} usuarios, {result['lecturas']} lecturas simuladas.")
    print(f"Contraseña de todas las cuentas de demostración: {DEMO_PASSWORD}")
    for u in USERS:
        print(f"  {u.username:<10} {u.role}")
    return 0


def check_incidents() -> int:
    from app.business.services.auto_incident_service import AutoIncidentService

    with SessionLocal() as session:
        created = AutoIncidentService(session).run()
    print(f"Incidencias automáticas abiertas: {len(created)}")
    for report in created:
        print(f"  #{report.id} {report.title}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Administración local del sistema de atrapanieblas")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="Crear un usuario administrador")
    admin.add_argument("--username", required=True)
    admin.add_argument("--full-name", default="Administrador del sistema")
    ensure = sub.add_parser("ensure-admin", help="Crear un administrador con contraseña temporal si no existe ninguno")
    ensure.add_argument("--username", default="admin")
    ensure.add_argument("--full-name", default="Administrador del sistema")
    sub.add_parser("seed-demo", help="Cargar datos de demostración (no disponible en producción)")
    sub.add_parser("check-incidents", help="Revisar ahora estaciones sin comunicación y sensores con lecturas anómalas")
    args = parser.parse_args()
    if args.command == "check-incidents":
        return check_incidents()
    if args.command == "seed-demo":
        return seed_demo()
    if args.command == "create-admin":
        return create_admin(args.username, args.full_name)
    if args.command == "ensure-admin":
        return ensure_admin(args.username, args.full_name)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
