import flet as ft
from datetime import datetime

from utils.config import Config, Style
from utils.credentials_store import list_credentials, get_credential, delete_credential
from utils.session import get_session_password
from .add_credential_modal import AddCredentialModal


class Credentials(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True)
        self.ref_page = page

        self.search_field = ft.TextField(
            **Style.search_field_params(), on_change=lambda _: self.load_credentials()
        )

        self.header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("Credentials", size=22, weight=ft.FontWeight.BOLD),
                ft.Row(
                    controls=[
                        ft.Container(
                            **Style.search_container_style(),
                            content=self.search_field,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ADD_OUTLINED,
                            tooltip="Add Credential",
                            icon_size=20,
                            on_click=self._on_add_click,
                        ),
                        ft.IconButton(
                            **Style.refresh_style(),
                            on_click=lambda _: self.load_credentials(),
                        ),
                    ],
                    spacing=5,
                ),
            ],
        )

        self.list_view = ft.ListView(expand=True, spacing=0)

        self.table = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                ft.Container(**_header_row_style()),
                self.list_view,
            ],
        )

        self.controls = [
            self.header,
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            ft.Container(
                **Style.flows_table_style(),
                content=self.table,
            ),
        ]

    def did_mount(self):
        self.load_credentials()

    def _current_owner(self) -> str | None:
        return self.ref_page.session.store.get("username")

    def load_credentials(self):
        owner = self._current_owner()
        if not owner:
            return

        query = (self.search_field.value or "").lower()
        rows = list_credentials(owner)
        if query:
            rows = [r for r in rows if query in r["name"].lower()]

        self.list_view.controls = [CredentialRow(r, self) for r in rows]

        if not rows:
            self.list_view.controls = [
                ft.Container(
                    padding=ft.Padding.all(20),
                    content=ft.Text(
                        "No credentials yet. Click the + to add one.",
                        italic=True,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                )
            ]

        if self.page:
            self.update()

    def _on_add_click(self, e):
        if not get_session_password():
            self._show_error(
                "Session expired — please log out and back in to add credentials."
            )
            return
        self.ref_page.show_dialog(AddCredentialModal(self.ref_page, self))

    def edit_credential(self, cred_meta: dict):
        password = get_session_password()
        if not password:
            self._show_error("Session expired — please log out and back in.")
            return

        decrypted = get_credential(self._current_owner(), cred_meta["id"], password)
        if decrypted is None:
            self._show_error(
                "Could not decrypt credential. The record may be corrupt or tied to a different password."
            )
            return

        self.ref_page.show_dialog(
            AddCredentialModal(
                self.ref_page, self, credential=cred_meta, decrypted=decrypted
            )
        )

    def delete_credential(self, cred_meta: dict):
        def on_confirm(_):
            delete_credential(self._current_owner(), cred_meta["id"])
            self.ref_page.pop_dialog()
            self.load_credentials()

        dlg = ft.AlertDialog(
            title=ft.Text("Delete Credential"),
            content=ft.Text(f"Delete '{cred_meta['name']}'? This cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self.ref_page.pop_dialog()),
                ft.Button(
                    "Delete",
                    style=ft.ButtonStyle(color="#ffffff", bgcolor=Config.RED),
                    on_click=on_confirm,
                ),
            ],
        )
        self.ref_page.show_dialog(dlg)

    def _show_error(self, msg: str):
        dlg = ft.AlertDialog(
            title=ft.Text("Error"),
            content=ft.Text(msg),
            actions=[ft.TextButton("OK", on_click=lambda _: self.ref_page.pop_dialog())],
        )
        self.ref_page.show_dialog(dlg)


class CredentialRow(ft.Container):
    def __init__(self, cred_meta: dict, parent: Credentials):
        super().__init__(
            padding=ft.Padding.symmetric(vertical=8, horizontal=15),
            border=ft.Border.only(
                bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
            ),
        )
        self.cred_meta = cred_meta
        self.parent_ref = parent

        created = cred_meta.get("created_at", "")
        try:
            created_display = datetime.fromisoformat(created).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            created_display = created or "-"

        self.content = ft.Row(
            controls=[
                ft.Text(cred_meta["name"], expand=True),
                ft.Text("••••••••", width=140, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(created_display, width=160, size=12),
                ft.Container(
                    width=110,
                    content=ft.Row(
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                icon_size=18,
                                tooltip="Edit",
                                on_click=lambda _: self.parent_ref.edit_credential(
                                    self.cred_meta
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=18,
                                tooltip="Delete",
                                icon_color=Config.RED,
                                on_click=lambda _: self.parent_ref.delete_credential(
                                    self.cred_meta
                                ),
                            ),
                        ],
                        spacing=0,
                    ),
                ),
            ]
        )


def _header_row_style() -> dict:
    return {
        "padding": ft.Padding.symmetric(vertical=10, horizontal=15),
        "border": ft.Border.only(
            bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
        ),
        "content": ft.Row(
            controls=[
                ft.Text("Name", weight=ft.FontWeight.BOLD, expand=True),
                ft.Text("Password", weight=ft.FontWeight.BOLD, width=140),
                ft.Text("Created", weight=ft.FontWeight.BOLD, width=160),
                ft.Text("Actions", weight=ft.FontWeight.BOLD, width=110),
            ]
        ),
    }
