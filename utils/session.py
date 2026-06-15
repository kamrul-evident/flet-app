_session_password: str | None = None
_session_owner: str | None = None


def set_session_password(password: str) -> None:
    global _session_password
    _session_password = password


def get_session_password() -> str | None:
    return _session_password


def set_session_owner(owner: str) -> None:
    global _session_owner
    _session_owner = owner


def get_session_owner() -> str | None:
    return _session_owner


def clear_session_password() -> None:
    global _session_password, _session_owner
    _session_password = None
    _session_owner = None
