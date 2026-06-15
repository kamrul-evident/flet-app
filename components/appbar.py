import flet as ft
from utils.auth import get_all_users, delete_user, reset_user_password, ADMIN_USERNAME
from utils.session import clear_session_password


class Appbar(ft.AppBar):
    def __init__(self, page):
        self._page = page
        username = page.session.store.get("username") or ""
        role = page.session.store.get("role") or ""

        actions = [
            ft.Text(
                username,
                size=16,
                margin=ft.Margin.only(right=10),
                weight=ft.FontWeight.W_600,
            ),
        ]

        if role == "admin_role":
            actions.append(
                ft.IconButton(
                    icon=ft.Icons.MANAGE_ACCOUNTS,
                    icon_size=18,
                    tooltip="User Management",
                    margin=ft.Margin.only(right=5),
                    on_click=self._show_user_management,
                ),
            )

        actions.extend(
            [
                ft.IconButton(
                    icon=ft.Icons.LOGOUT,
                    icon_size=16,
                    tooltip="Logout",
                    margin=ft.Margin.only(right=10),
                    on_click=self._logout,
                ),
                ft.IconButton(
                    icon_size=16,
                    icon=ft.Icons.LIGHT_MODE
                    if page.theme_mode == ft.ThemeMode.DARK
                    else ft.Icons.DARK_MODE,
                    tooltip="Theme",
                    margin=ft.Margin.only(right=20),
                    on_click=lambda e: self._switch_theme(e),
                ),
            ]
        )

        super().__init__(
            leading=ft.Container(
                padding=ft.Padding.only(left=10),
                content=ft.Image(src="icon.png", width=40, height=40),
            ),
            leading_width=60,
            toolbar_height=56,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
            actions=actions,
        )

    # ── Logout ──────────────────────────────────────────────────────
    async def _logout(self, e):
        self.page.session.store.clear()
        clear_session_password()
        await self.page.push_route("/login")

    # ── Theme toggle ────────────────────────────────────────────────
    def _switch_theme(self, e):
        self.page.theme_mode = (
            ft.ThemeMode.DARK
            if self.page.theme_mode == ft.ThemeMode.LIGHT
            else ft.ThemeMode.LIGHT
        )
        e.control.icon = (
            ft.Icons.LIGHT_MODE
            if self.page.theme_mode == ft.ThemeMode.DARK
            else ft.Icons.DARK_MODE
        )

    # ── User Management ─────────────────────────────────────────────
    def _show_user_management(self, e):
        users = get_all_users()
        user_list = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO)

        def _build_user_rows():
            user_list.controls.clear()
            for user in users:
                is_admin = user["username"] == ADMIN_USERNAME
                already_reset = user.get("must_change_password", False)

                action_controls = []
                if not is_admin:
                    reset_btn = ft.IconButton(
                        icon=ft.Icons.LOCK_RESET,
                        icon_size=18,
                        icon_color="#f0883e" if not already_reset else ft.Colors.WHITE_24,
                        tooltip="Password already reset" if already_reset else "Reset Password",
                        disabled=already_reset,
                        on_click=lambda _, u=user["username"]: _confirm_reset(u),
                    )
                    action_controls.append(reset_btn)
                    action_controls.append(
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=18,
                            icon_color="#f85149",
                            tooltip="Delete User",
                            on_click=lambda _, u=user["username"]: _confirm_delete(u),
                        ),
                    )

                status_text = user["role"]
                if already_reset:
                    status_text += " · password reset pending"

                row = ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text(
                                    user["username"], size=13, weight=ft.FontWeight.W_500
                                ),
                                ft.Text(status_text, size=11),
                            ],
                        ),
                        ft.Row(spacing=0, controls=action_controls),
                    ],
                )
                user_list.controls.append(row)
                user_list.controls.append(ft.Divider(height=1))

        def _refresh():
            nonlocal users
            users = get_all_users()
            _build_user_rows()
            user_list.update()

        def _confirm_delete(username):
            confirm_dlg = ft.AlertDialog(
                title=ft.Text("Delete User"),
                content=ft.Text(f"Are you sure you want to delete {username}?"),
                actions=[
                    ft.TextButton(
                        "Cancel",
                        on_click=lambda _: self.page.pop_dialog(),
                    ),
                    ft.TextButton(
                        "Delete",
                        style=ft.ButtonStyle(color="#f85149"),
                        on_click=lambda _: _do_delete(username),
                    ),
                ],
            )
            self.page.show_dialog(confirm_dlg)

        def _do_delete(username):
            delete_user(username)
            self.page.pop_dialog()
            _refresh()

        def _confirm_reset(username):
            confirm_dlg = ft.AlertDialog(
                title=ft.Text("Reset Password"),
                content=ft.Text(
                    f"Reset password for {username}?\n\n"
                    "The user will be asked to set a new password on next login."
                ),
                actions=[
                    ft.TextButton(
                        "Cancel",
                        on_click=lambda _: self.page.pop_dialog(),
                    ),
                    ft.TextButton(
                        "Reset",
                        style=ft.ButtonStyle(color="#f0883e"),
                        on_click=lambda _: _do_reset(username),
                    ),
                ],
            )
            self.page.show_dialog(confirm_dlg)

        def _do_reset(username):
            reset_user_password(username)
            self.page.pop_dialog()
            _refresh()

        _build_user_rows()

        dlg = ft.AlertDialog(
            title=ft.Text("User Management"),
            content=ft.Container(
                width=450,
                height=400,
                content=user_list,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)
