import flet as ft
from utils import Config
from utils.cli_runner import (
    launch_duckdb_cli_async,
    launch_polars_cli_async,
    launch_python_cli_async,
    kill_cli_async,
)
from components import Flows, Appbar, SidebarItem, Credentials
from utils.license_validator import get_license_info, activate_license
from utils.hwid import get_hwid_display
import asyncio


class HomeView(ft.View):
    def __init__(self, page: ft.Page, active_item="Flows"):
        super().__init__(padding=0, appbar=Appbar(page=page))

        # Check role
        is_admin = page.session.store.get("role") == "admin_role"

        # Content blocks
        self.flows_content = Flows(page)
        self.credentials_content = Credentials(page)

        is_flows_active = active_item != "Credentials"

        # Store references for SidebarItems that need dynamic toggling
        self.flows_item = SidebarItem(
            ft.Icons.ACCOUNT_TREE_OUTLINED,
            "Flows",
            is_active=is_flows_active,
            on_click=self._handle_flows_click,
        )
        self.credentials_item = SidebarItem(
            ft.Icons.VPN_KEY_OUTLINED,
            "Credentials",
            is_active=active_item == "Credentials",
            on_click=self._handle_credentials_click,
        )
        self.duckdb_item = SidebarItem(
            ft.Icons.STORAGE,
            "Sql Engine CLI",
            on_click=self._handle_duckdb_click,
        )
        self.duckdb_item.visible = is_admin
        self.polars_item = SidebarItem(
            ft.Icons.PEST_CONTROL_RODENT,
            "Data Engine CLI",
            on_click=self._handle_polars_click,
        )
        self.polars_item.visible = is_admin
        self.python_item = SidebarItem(
            ft.Icons.TERMINAL,
            "Python CLI",
            on_click=self._handle_python_click,
        )

        # --- License info ---
        self._license_info = get_license_info()
        self._license_info_column = ft.Column(spacing=2)
        self._build_license_info_controls()

        # --- Sidebar ---
        self.sidebar = ft.Container(
            width=250,
            bgcolor=Config.SIDEBAR_BG,
            padding=10,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.Divider(),
                    self.flows_item,
                    self.credentials_item,
                    self.python_item,
                    self.duckdb_item,
                    self.polars_item,
                    ft.Container(
                        expand=True
                    ),  # Spacer to push license info to the bottom
                    ft.GestureDetector(
                        mouse_cursor=ft.MouseCursor.CLICK,
                        on_tap=self._show_license_dialog,
                        content=ft.Container(
                            padding=ft.Padding.symmetric(horizontal=15, vertical=10),
                            border=ft.Border.only(
                                top=ft.border.BorderSide(1, Config.BORDER)
                            ),
                            content=self._license_info_column,
                        ),
                    ),
                ],
            ),
        )

        # --- Main Content ---

        initial_content = (
            self.credentials_content
            if active_item == "Credentials"
            else self.flows_content
        )

        self.main_content = ft.Container(
            expand=True, padding=ft.Padding.all(20), content=initial_content
        )

        # --- Assembly ---
        self.controls = [
            ft.Row(expand=True, spacing=0, controls=[self.sidebar, self.main_content])
        ]

    def _build_license_info_controls(self):
        """Build sidebar license info controls from current license data."""
        self._license_info_column.controls.clear()
        info = self._license_info
        if not info:
            return

        is_trial = info.get("is_trial", False)
        tier = info.get("tier", "Basic")

        if is_trial:
            self._license_info_column.controls.append(
                ft.Text("Trial", size=12, color="#f0883e", weight=ft.FontWeight.W_600)
            )
        else:
            self._license_info_column.controls.append(
                ft.Text(
                    info["customer_name"],
                    size=12,
                    color=ft.Colors.WHITE_70,
                    weight=ft.FontWeight.W_500,
                )
            )
            self._license_info_column.controls.append(
                ft.Text(tier, size=11, color="#4a90d9", weight=ft.FontWeight.W_500)
            )

        if info["days_left"] is not None:
            days = info["days_left"]
            if days <= 14:
                color = Config.RED
            elif days <= 30:
                color = Config.YELLOW
            else:
                color = ft.Colors.WHITE_54
            self._license_info_column.controls.append(
                ft.Text(f"{days} days remaining", size=11, color=color)
            )
        else:
            self._license_info_column.controls.append(
                ft.Text("Perpetual license", size=11, color=ft.Colors.WHITE54)
            )

    def _refresh_license_info(self):
        """Re-read license and update sidebar display."""
        self._license_info = get_license_info()
        self._build_license_info_controls()
        self._license_info_column.update()

    def _show_license_dialog(self):
        info = self._license_info
        if not info:
            return

        is_trial = info.get("is_trial", False)
        tier = info.get("tier", "Basic")
        max_flows = info.get("max_flows")
        days_left = info.get("days_left")

        rows = []

        if not is_trial:
            rows.append(
                self._dialog_row("Customer", info.get("customer_name", "Unknown"))
            )

        rows.append(self._dialog_row("Tier", tier))
        rows.append(
            self._dialog_row(
                "Max Flows",
                str(max_flows) if max_flows is not None else "Unlimited",
            )
        )

        if days_left is not None:
            rows.append(self._dialog_row("Days Remaining", str(days_left)))
            rows.append(self._dialog_row("Expires", info.get("expiration", "")[:10]))
        else:
            rows.append(self._dialog_row("Expiration", "Perpetual"))

        # Hardware ID with copy button
        hwid = get_hwid_display()
        hwid_field = ft.TextField(
            value=hwid,
            read_only=True,
            multiline=True,
            min_lines=3,
            text_size=12,
            expand=True,
        )

        # License key input + activate
        key_field = ft.TextField(
            label="License Key",
            hint_text="Paste your DRYX-... key here",  # noqa
            prefix_icon=ft.Icons.VPN_KEY_OUTLINED,
            multiline=True,
            min_lines=3,
            max_lines=5,
            text_size=12,
            width=400,
        )
        status_msg = ft.Text("", size=12, visible=False)

        def on_activate(_):
            key = key_field.value.strip()
            if not key:
                status_msg.value = "Please paste your license key"
                status_msg.color = "#f85149"
                status_msg.visible = True
                status_msg.update()
                return

            success, message = activate_license(key)
            if success:
                status_msg.value = "License activated successfully!"
                status_msg.color = "#3fb950"
                status_msg.visible = True
                status_msg.update()
                self._refresh_license_info()
            else:
                status_msg.value = message
                status_msg.color = "#f85149"
                status_msg.visible = True
                status_msg.update()

        dlg = ft.AlertDialog(
            title=ft.Text("License Information"),
            content=ft.Column(
                controls=[
                    *rows,
                    ft.Divider(height=16),
                    ft.Text("Hardware ID:", size=12, weight=ft.FontWeight.W_600),
                    ft.Stack(
                        [
                            hwid_field,
                            ft.IconButton(
                                icon=ft.Icons.COPY,
                                icon_size=16,
                                tooltip="Copy",
                                on_click=lambda _: ft.Clipboard().set(hwid),
                                bottom=2,
                                right=2,
                            ),
                        ],
                    ),
                    ft.Divider(height=16),
                    ft.Text("Activate License:", size=12, weight=ft.FontWeight.W_600),
                    key_field,
                    ft.Button(
                        "Activate",
                        on_click=on_activate,
                    ),
                    status_msg,
                ],
                spacing=8,
                tight=True,
                width=400,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)

    @staticmethod
    def _dialog_row(label: str, value: str) -> ft.Row:
        return ft.Row(
            controls=[
                ft.Text(f"{label}:", size=13, weight=ft.FontWeight.W_600, width=120),
                ft.Text(value, size=13),
            ],
            spacing=10,
        )

    async def _handle_flows_click(self):
        if self.flows_item.is_active:
            return

        self.flows_item.is_active = True
        self.credentials_item.is_active = False

        self.main_content.content = self.flows_content
        self.main_content.update()

        await ft.SharedPreferences().set("active_home_item", "Flows")

    async def _handle_credentials_click(self, e):
        if self.credentials_item.is_active:
            return

        self.credentials_item.is_active = True
        self.flows_item.is_active = False

        self.main_content.content = self.credentials_content
        self.main_content.update()

        await e.page.shared_preferences.set("active_home_item", "Credentials")

    def _handle_duckdb_click(self):
        if self.duckdb_item.is_active:
            # User wants to close it by clicking again
            asyncio.create_task(kill_cli_async("duckdb"))
            self.duckdb_item.is_active = False
            self.sidebar.update()
            return

        self.duckdb_item.is_active = True

        def _on_closed():
            self.duckdb_item.is_active = False
            try:
                self.sidebar.update()
            except Exception:
                pass

        # Run asynchronously
        asyncio.create_task(launch_duckdb_cli_async(_on_closed))

    def _handle_polars_click(self):
        if self.polars_item.is_active:
            # User wants to close it by clicking again
            asyncio.create_task(kill_cli_async("polars"))
            self.polars_item.is_active = False
            self.sidebar.update()
            return

        self.polars_item.is_active = True

        def _on_closed():
            self.polars_item.is_active = False
            try:
                self.sidebar.update()
            except Exception:
                pass

        asyncio.create_task(launch_polars_cli_async(_on_closed))

    def _handle_python_click(self):
        if self.python_item.is_active:
            # User wants to close it by clicking again
            asyncio.create_task(kill_cli_async("python"))
            self.python_item.is_active = False
            self.sidebar.update()
            return

        self.python_item.is_active = True

        def _on_closed():
            try:
                self.python_item.is_active = False
                self.sidebar.update()
            except Exception:
                pass

        asyncio.create_task(launch_python_cli_async(_on_closed))
