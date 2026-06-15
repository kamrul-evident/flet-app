import os
import sqlite3
from datetime import datetime
from .credentials_crypto import encrypt_credential, decrypt_credential

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "dataryx.db")


def _get_conn():
    return sqlite3.connect(DB_PATH)


def init_credentials():
    """Create the credentials table if it does not exist."""
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL,
            name TEXT NOT NULL,
            enc_blob BLOB NOT NULL,
            nonce BLOB NOT NULL,
            kdf_salt BLOB NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(owner, name)
        )
        """
    )
    conn.commit()
    conn.close()


def add_credential(
    owner: str, name: str, fields: dict, password: str
) -> tuple[bool, str]:
    """Encrypt and insert a new credential for this user."""
    ciphertext, nonce, kdf_salt = encrypt_credential(fields, password)
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO credentials (owner, name, enc_blob, nonce, kdf_salt, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (owner, name, ciphertext, nonce, kdf_salt, datetime.now().isoformat()),
        )
        conn.commit()
        return True, "Credential saved"
    except sqlite3.IntegrityError:
        return False, "A credential with this name already exists"
    finally:
        conn.close()


def update_credential(
    owner: str, cred_id: int, name: str, fields: dict, password: str
) -> tuple[bool, str]:
    """Re-encrypt and update an existing credential (must belong to owner)."""
    ciphertext, nonce, kdf_salt = encrypt_credential(fields, password)
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "UPDATE credentials SET name = ?, enc_blob = ?, nonce = ?, kdf_salt = ? "
            "WHERE id = ? AND owner = ?",
            (name, ciphertext, nonce, kdf_salt, cred_id, owner),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return False, "Credential not found"
        return True, "Credential updated"
    except sqlite3.IntegrityError:
        return False, "A credential with this name already exists"
    finally:
        conn.close()


def delete_credential(owner: str, cred_id: int) -> bool:
    """Delete a credential (must belong to owner)."""
    conn = _get_conn()
    cursor = conn.execute(
        "DELETE FROM credentials WHERE id = ? AND owner = ?", (cred_id, owner)
    )
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def list_credentials(owner: str) -> list[dict]:
    """Return credential metadata (no secrets) for this user."""
    conn = _get_conn()
    cursor = conn.execute(
        "SELECT id, name, created_at FROM credentials WHERE owner = ? ORDER BY name",
        (owner,),
    )
    result = [
        {"id": row[0], "name": row[1], "created_at": row[2]}
        for row in cursor.fetchall()
    ]
    conn.close()
    return result


def get_credential(owner: str, cred_id: int, password: str) -> dict | None:
    """Fetch and decrypt a single credential. Returns None if not found or decryption fails."""
    conn = _get_conn()
    cursor = conn.execute(
        "SELECT enc_blob, nonce, kdf_salt FROM credentials WHERE id = ? AND owner = ?",
        (cred_id, owner),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return decrypt_credential(row[0], row[1], row[2], password)
    except Exception:
        return None
