from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
import hashlib


class Permission(str, Enum):
    READ = "r"
    WRITE = "w"
    EXECUTE = "x"


@dataclass
class User:
    username: str
    password_hash: str
    is_admin: bool = False


@dataclass
class Session:
    user: User
    cwd: str = "/"


@dataclass
class FSNode:
    name: str
    owner: str
    is_dir: bool
    content: str = ""
    children: Dict[str, "FSNode"] = field(default_factory=dict)
    acl: Dict[str, Set[Permission]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Propietario con control completo por defecto
        self.acl.setdefault(self.owner, {Permission.READ, Permission.WRITE, Permission.EXECUTE})


class AuthError(Exception):
    pass


class AccessError(Exception):
    pass


class NotFoundError(Exception):
    pass


class AuthManager:
    def __init__(self) -> None:
        self.users: Dict[str, User] = {}
        self._seed_admin()

    def _seed_admin(self) -> None:
        self.register("admin", "admin123", is_admin=True)

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def register(self, username: str, password: str, is_admin: bool = False) -> User:
        if username in self.users:
            raise AuthError("El usuario ya existe")
        user = User(username=username, password_hash=self._hash_password(password), is_admin=is_admin)
        self.users[username] = user
        return user

    def login(self, username: str, password: str) -> Session:
        user = self.users.get(username)
        if not user:
            raise AuthError("Usuario no encontrado")
        if user.password_hash != self._hash_password(password):
            raise AuthError("Credenciales inválidas")
        return Session(user=user)


class FileSystem:
    def __init__(self) -> None:
        self.root = FSNode(name="/", owner="admin", is_dir=True)

    def _normalize(self, cwd: str, path: str) -> str:
        if path.startswith("/"):
            absolute = path
        else:
            absolute = f"{cwd.rstrip('/')}/{path}" if cwd != "/" else f"/{path}"

        parts: List[str] = []
        for part in absolute.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/" + "/".join(parts)

    def _split(self, path: str) -> List[str]:
        return [p for p in path.split("/") if p]

    def get_node(self, path: str) -> FSNode:
        if path == "/":
            return self.root
        node = self.root
        for part in self._split(path):
            if not node.is_dir or part not in node.children:
                raise NotFoundError(f"Ruta no encontrada: {path}")
            node = node.children[part]
        return node

    def _has_perm(self, node: FSNode, username: str, permission: Permission, is_admin: bool) -> bool:
        if is_admin:
            return True
        return permission in node.acl.get(username, set())

    def _assert_perm(self, node: FSNode, username: str, permission: Permission, is_admin: bool) -> None:
        if not self._has_perm(node, username, permission, is_admin):
            raise AccessError(f"Permiso denegado: falta '{permission.value}' en {node.name}")

    def mkdir(self, cwd: str, path: str, username: str, is_admin: bool) -> str:
        abs_path = self._normalize(cwd, path)
        parent_path = "/" + "/".join(self._split(abs_path)[:-1]) if len(self._split(abs_path)) > 1 else "/"
        dirname = self._split(abs_path)[-1]
        parent = self.get_node(parent_path)
        self._assert_perm(parent, username, Permission.WRITE, is_admin)
        if dirname in parent.children:
            raise AccessError("Ya existe un archivo o carpeta con ese nombre")
        parent.children[dirname] = FSNode(name=dirname, owner=username, is_dir=True)
        return abs_path

    def touch(self, cwd: str, path: str, username: str, is_admin: bool) -> str:
        abs_path = self._normalize(cwd, path)
        parent_path = "/" + "/".join(self._split(abs_path)[:-1]) if len(self._split(abs_path)) > 1 else "/"
        filename = self._split(abs_path)[-1]
        parent = self.get_node(parent_path)
        self._assert_perm(parent, username, Permission.WRITE, is_admin)
        if filename not in parent.children:
            parent.children[filename] = FSNode(name=filename, owner=username, is_dir=False)
        return abs_path

    def ls(self, cwd: str, path: str, username: str, is_admin: bool) -> List[str]:
        abs_path = self._normalize(cwd, path)
        node = self.get_node(abs_path)
        self._assert_perm(node, username, Permission.READ, is_admin)
        if node.is_dir:
            return sorted(node.children.keys())
        return [node.name]

    def cd(self, cwd: str, path: str, username: str, is_admin: bool) -> str:
        abs_path = self._normalize(cwd, path)
        node = self.get_node(abs_path)
        if not node.is_dir:
            raise AccessError("No es una carpeta")
        self._assert_perm(node, username, Permission.EXECUTE, is_admin)
        return abs_path

    def write_file(self, cwd: str, path: str, content: str, username: str, is_admin: bool) -> str:
        abs_path = self._normalize(cwd, path)
        node = self.get_node(abs_path)
        if node.is_dir:
            raise AccessError("No se puede escribir en una carpeta")
        self._assert_perm(node, username, Permission.WRITE, is_admin)
        node.content = content
        return abs_path

    def read_file(self, cwd: str, path: str, username: str, is_admin: bool) -> str:
        abs_path = self._normalize(cwd, path)
        node = self.get_node(abs_path)
        if node.is_dir:
            raise AccessError("No se puede leer una carpeta como archivo")
        self._assert_perm(node, username, Permission.READ, is_admin)
        return node.content

    def grant(self, cwd: str, path: str, owner_user: str, target_user: str, perms: Set[Permission], is_admin: bool) -> str:
        abs_path = self._normalize(cwd, path)
        node = self.get_node(abs_path)
        if not is_admin and node.owner != owner_user:
            raise AccessError("Solo el propietario o admin puede conceder permisos")
        node.acl.setdefault(target_user, set()).update(perms)
        return abs_path


class MiniOS:
    def __init__(self) -> None:
        self.auth = AuthManager()
        self.fs = FileSystem()
        self.session: Optional[Session] = None

    def _require_login(self) -> Session:
        if not self.session:
            raise AuthError("Debes iniciar sesión primero")
        return self.session

    def handle(self, raw: str) -> str:
        tokens = raw.strip().split()
        if not tokens:
            return ""
        cmd, *args = tokens

        if cmd == "register":
            if len(args) < 2:
                return "Uso: register <usuario> <password>"
            self.auth.register(args[0], args[1])
            return f"Usuario '{args[0]}' creado"

        if cmd == "login":
            if len(args) < 2:
                return "Uso: login <usuario> <password>"
            self.session = self.auth.login(args[0], args[1])
            return f"Sesión iniciada como {args[0]}"

        if cmd == "logout":
            self.session = None
            return "Sesión cerrada"

        try:
            session = self._require_login()
            username = session.user.username
            is_admin = session.user.is_admin

            if cmd == "pwd":
                return session.cwd

            if cmd == "whoami":
                return f"{username}{' (admin)' if is_admin else ''}"

            if cmd == "mkdir":
                path = args[0]
                created = self.fs.mkdir(session.cwd, path, username, is_admin)
                return f"Carpeta creada: {created}"

            if cmd == "touch":
                path = args[0]
                created = self.fs.touch(session.cwd, path, username, is_admin)
                return f"Archivo listo: {created}"

            if cmd == "ls":
                path = args[0] if args else "."
                items = self.fs.ls(session.cwd, path, username, is_admin)
                return "\n".join(items) if items else "(vacío)"

            if cmd == "cd":
                path = args[0]
                new_path = self.fs.cd(session.cwd, path, username, is_admin)
                session.cwd = new_path
                return f"Directorio actual: {new_path}"

            if cmd == "write":
                if len(args) < 2:
                    return "Uso: write <archivo> <texto...>"
                path = args[0]
                content = " ".join(args[1:])
                written = self.fs.write_file(session.cwd, path, content, username, is_admin)
                return f"Contenido actualizado en: {written}"

            if cmd == "cat":
                path = args[0]
                return self.fs.read_file(session.cwd, path, username, is_admin)

            if cmd == "grant":
                if len(args) < 3:
                    return "Uso: grant <ruta> <usuario> <permisos (rwx)>"
                path, target_user, perm_str = args[0], args[1], args[2]
                perms = {Permission(ch) for ch in perm_str if ch in {"r", "w", "x"}}
                if not perms:
                    return "Permisos inválidos. Usa combinaciones de r, w, x"
                self.fs.grant(session.cwd, path, username, target_user, perms, is_admin)
                return f"Permisos {perm_str} concedidos sobre {path} a {target_user}"

            if cmd == "help":
                return (
                    "Comandos:\n"
                    "  register <u> <p>\n"
                    "  login <u> <p> | logout\n"
                    "  whoami | pwd\n"
                    "  mkdir <ruta> | touch <ruta>\n"
                    "  ls [ruta] | cd <ruta>\n"
                    "  write <archivo> <texto> | cat <archivo>\n"
                    "  grant <ruta> <usuario> <rwx>\n"
                    "  help | exit"
                )

            if cmd == "exit":
                raise SystemExit

            return "Comando no reconocido. Usa 'help'."

        except (AuthError, AccessError, NotFoundError, IndexError, ValueError) as exc:
            return f"Error: {exc}"


def run_cli() -> None:
    system = MiniOS()
    print("MiniOS - Gestión de Accesos (escribe 'help' para ayuda)")
    while True:
        try:
            prompt_user = system.session.user.username if system.session else "guest"
            prompt_cwd = system.session.cwd if system.session else "/"
            raw = input(f"{prompt_user}:{prompt_cwd}$ ")
            out = system.handle(raw)
            if out:
                print(out)
        except (KeyboardInterrupt, EOFError, SystemExit):
            print("\nSaliendo...")
            break


if __name__ == "__main__":
    run_cli()
