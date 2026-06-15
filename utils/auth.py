import os
import re
import sqlite3
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "dataryx.db")

ADMIN_USERNAME = "admin"
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


def validate_username(username: str) -> tuple[bool, str]:
    """Username must be 3-32 chars, alphanumeric or underscore."""
    if not USERNAME_REGEX.match(username):
        return False, "Username must be 3-32 chars (letters, numbers, underscore)"
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """Password must be at least 8 chars, 1 uppercase, 1 digit, 1 special char."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password):
        return False, "Password must contain at least one special character"
    return True, ""


def hash_password(password: str, salt: bytes) -> str:
    """Hashes a password using PBKDF2HMAC and returns a base64 encoded string."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
        backend=default_backend()
    )
    key = kdf.derive(password.encode('utf-8'))
    return base64.b64encode(key).decode('utf-8')


def _get_conn():
    return sqlite3.connect(DB_PATH)


def init_users():
    """Migrate database — rename email→username, add must_change_password if missing."""
    conn = _get_conn()
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    if "email" in columns and "username" not in columns:
        conn.execute("ALTER TABLE users RENAME COLUMN email TO username")
        conn.commit()
        # Rewrite admin identifier if the legacy default still exists.
        conn.execute(
            "UPDATE users SET username = ? WHERE username = ?",
            (ADMIN_USERNAME, "admin@gmail.com"),
        )
        conn.commit()

    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    if "must_change_password" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    conn.close()


def verify_user(username: str, password: str) -> dict | None:
    """
    Verifies credentials against the database.
    Returns {"username", "role", "must_change_password"} on success, None on failure.
    """
    try:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT salt, hash, role, must_change_password FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        salt = base64.b64decode(row[0].encode('utf-8'))
        stored_hash = row[1]
        role = row[2]
        must_change = bool(row[3])

        if hash_password(password, salt) == stored_hash:
            return {"username": username, "role": role, "must_change_password": must_change}
        return None
    except Exception:
        return None


def user_exists(username: str) -> bool:
    """Check if a user with this username already exists."""
    conn = _get_conn()
    cursor = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def add_user(username: str, password: str, role: str = "user_role") -> tuple[bool, str]:
    """Create a new user. Returns (success, message)."""
    if user_exists(username):
        return False, "User with this username already exists"

    salt = os.urandom(16)
    hashed = hash_password(password, salt)
    salt_b64 = base64.b64encode(salt).decode('utf-8')

    conn = _get_conn()
    conn.execute(
        "INSERT INTO users (username, salt, hash, role, must_change_password) VALUES (?, ?, ?, ?, 0)",
        (username, salt_b64, hashed, role),
    )
    conn.commit()
    conn.close()
    return True, "User created successfully"


def delete_user(username: str) -> bool:
    """Delete a user. Cannot delete the admin account."""
    if username == ADMIN_USERNAME:
        return False

    conn = _get_conn()
    cursor = conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def check_must_change_password(username: str) -> bool:
    """Check if user needs to change password."""
    conn = _get_conn()
    cursor = conn.execute(
        "SELECT must_change_password FROM users WHERE username = ?", (username,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    return bool(row[0])


def reset_user_password(username: str) -> bool:
    """Flag user to change password on next login."""
    conn = _get_conn()
    cursor = conn.execute(
        "UPDATE users SET must_change_password = 1 WHERE username = ?",
        (username,),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def change_password(username: str, new_password: str) -> bool:
    """Set new password and clear must_change_password flag."""
    salt = os.urandom(16)
    hashed = hash_password(new_password, salt)
    salt_b64 = base64.b64encode(salt).decode('utf-8')

    conn = _get_conn()
    cursor = conn.execute(
        "UPDATE users SET salt = ?, hash = ?, must_change_password = 0 WHERE username = ?",
        (salt_b64, hashed, username),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def get_all_users() -> list[dict]:
    """Return all users (without secrets)."""
    conn = _get_conn()
    cursor = conn.execute("SELECT username, role, must_change_password FROM users")
    users = [
        {"username": row[0], "role": row[1], "must_change_password": bool(row[2])}
        for row in cursor.fetchall()
    ]
    conn.close()
    return users
