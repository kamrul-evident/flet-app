import flet as ft
import asyncio

from utils.config import Config, Style
from utils.credentials_store import add_credential, update_credential
from utils.db_url import build_sqlalchemy_url
from utils.session import get_session_password


DB_TYPES = ["PostgreSQL", "MySQL", "MariaDB", "MSSQL", "Oracle", "DB2"]

_DEFAULT_PORTS = {
    "PostgreSQL": "5432",
    "MySQL": "3306",
    "MariaDB": "3306",
    "MSSQL": "1433",
    "Oracle": "1521",
    "DB2": "50000",
}


class AddCredentialModal(ft.AlertDialog):
    def __init__(
        self, page: ft.Page, parent, credential: dict = None, decrypted: dict = None
    ):
        """
        credential: row metadata (id, name, created_at) for edit mode, else None
        decrypted:  decrypted payload dict for edit mode, else None
        """
        super().__init__(**Style.dialog_style())
        self.page_ref = page
        self.parent_ref = parent
        self.edit_credential = credential

        is_edit = credential is not None

        self.title = ft.Row(
            [
                ft.Icon(
                    ft.Icons.EDIT_ROUNDED if is_edit else ft.Icons.VPN_KEY_ROUNDED,
                    color=Config.SIDEBAR_BG,
                    size=20,
                ),
                ft.Text(
                    "Edit Credential" if is_edit else "Add Credential",
                    size=16,
                    weight=ft.FontWeight.W_600,
                ),
            ],
            spacing=10,
        )

        # ── Fields ──
        self.name_field = ft.TextField(
            label="Name",
            hint_text="e.g. Analytics Prod",
            expand=True,
            height=70,
            helper=" ",
            offset=ft.Offset(0, 0.15),
        )
        self.db_type_field = ft.Dropdown(
            label="Database Type",
            options=[ft.dropdown.Option(t) for t in DB_TYPES],
            value="PostgreSQL",
            width=200,
            on_select=self._on_db_type_change,
        )
        self.user_field = ft.TextField(
            label="Username", expand=True, height=70, helper=" "
        )
        self.password_field = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            expand=True,
            height=70,
            helper=" ",
        )
        self.host_field = ft.TextField(
            label="Host",
            hint_text="db.example.com",
            expand=True,
            height=70,
            helper=" ",
        )
        self.port_field = ft.TextField(
            label="Port",
            value=_DEFAULT_PORTS["PostgreSQL"],
            keyboard_type=ft.KeyboardType.NUMBER,
            width=120,
            height=70,
            helper=" ",
        )
        self.database_field = ft.TextField(
            label="Database", expand=True, height=70, helper=" "
        )

        self.status_msg = ft.Text("", size=12, visible=False)

        # Pre-fill for edit
        if is_edit:
            self.name_field.value = credential.get("name", "")
            if decrypted:
                self.db_type_field.value = decrypted.get("db_type", "PostgreSQL")
                self.user_field.value = decrypted.get("user", "")
                self.password_field.value = decrypted.get("password", "")
                self.host_field.value = decrypted.get("host", "")
                self.port_field.value = str(decrypted.get("port", ""))
                self.database_field.value = decrypted.get("database", "")

        self.content = ft.Column(
            **Style.dialog_content_style(),
            controls=[
                ft.Divider(height=1, color=Config.BORDER),
                ft.Row(
                    [self.name_field, self.db_type_field],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row([self.user_field]),
                ft.Row([self.password_field]),
                ft.Row([self.host_field, self.port_field]),
                ft.Row([self.database_field]),
                self.status_msg,
            ],
        )

        self.actions = [
            ft.Button(
                **Style.dialog_cancel_button_style(),
                on_click=lambda e: page.pop_dialog(),
            ),
            ft.Button(
                content="Test Connection",
                icon=ft.Icons.NETWORK_CHECK,
                height=40,
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: Config.BORDER},
                    color={ft.ControlState.DEFAULT: "#ffffff"},
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding.symmetric(horizontal=20, vertical=12),
                ),
                on_click=self._on_test_connection,
            ),
            ft.Button(
                **Style.dialog_save_button_style(),
                content="Update" if is_edit else "Save",
                on_click=self._on_save,
            ),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _on_db_type_change(self, e):
        # An Auto-fill the default port only if the port field still holds a previous default.
        if (
            self.port_field.value in _DEFAULT_PORTS.values()
            or not self.port_field.value
        ):
            self.port_field.value = _DEFAULT_PORTS.get(
                self.db_type_field.value, self.port_field.value
            )
            self.port_field.update()

    def _collect_fields(self) -> dict | None:
        for field in (
            self.name_field,
            self.user_field,
            self.password_field,
            self.host_field,
            self.port_field,
            self.database_field,
        ):
            field.error = None

        if not self.name_field.value:
            self.name_field.error = "Required"
            self.update()
            return None
        if not self.user_field.value:
            self.user_field.error = "Required"
            self.update()
            return None
        if not self.password_field.value:
            self.password_field.error = "Required"
            self.update()
            return None
        if not self.host_field.value:
            self.host_field.error = "Required"
            self.update()
            return None
        try:
            port = int(self.port_field.value)
            if port < 1 or port > 65535:
                raise ValueError
        except (ValueError, TypeError):
            self.port_field.error = "1-65535"
            self.update()
            return None
        if not self.database_field.value:
            self.database_field.error = "Required"
            self.update()
            return None

        return {
            "db_type": self.db_type_field.value,
            "user": self.user_field.value,
            "password": self.password_field.value,
            "host": self.host_field.value,
            "port": port,
            "database": self.database_field.value,
        }

    def _set_status(self, text: str, color: str):
        self.status_msg.value = text
        self.status_msg.color = color
        self.status_msg.visible = True
        self.status_msg.update()

    async def _on_test_connection(self, e):
        fields = self._collect_fields()
        if fields is None:
            return

        self._set_status("Testing connection...", Config.MUTED)

        # DB2 and Oracle require a FROM clause; others accept bare SELECT 1.
        test_queries = {
            "DB2": "SELECT 1 FROM SYSIBM.SYSDUMMY1",
            "Oracle": "SELECT 1 FROM DUAL",
        }
        test_sql = test_queries.get(fields["db_type"], "SELECT 1")

        def _attempt():
            try:
                from sqlalchemy import create_engine, text

                url = build_sqlalchemy_url(fields["db_type"], fields)
                engine = create_engine(url, pool_pre_ping=True)
                with engine.connect() as conn:
                    conn.execute(text(test_sql))
                engine.dispose()
                return True, "Connection OK"
            except Exception as exc:
                msg = str(exc).splitlines()[0][:200]
                return False, msg

        ok, msg = await asyncio.to_thread(_attempt)
        self._set_status(msg, Config.GREEN if ok else Config.RED)

    def _on_save(self, e):
        fields = self._collect_fields()
        if fields is None:
            return

        password = get_session_password()
        if not password:
            self._set_status(
                "Session expired — please log out and back in.", Config.RED
            )
            return

        owner = self.page_ref.session.store.get("username")
        name = self.name_field.value

        if self.edit_credential:
            ok, msg = update_credential(
                owner, self.edit_credential["id"], name, fields, password
            )
        else:
            ok, msg = add_credential(owner, name, fields, password)

        if not ok:
            self._set_status(msg, Config.RED)
            return

        self.page_ref.pop_dialog()
        self.parent_ref.load_credentials()
