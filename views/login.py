import flet as ft
from utils import LoginStyle
from utils.auth import (
    init_users,
    verify_user,
    change_password,
    check_must_change_password,
    validate_password,
    validate_username,
)
from utils.credentials_store import init_credentials
from utils.session import set_session_password, set_session_owner


class LoginView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__(**LoginStyle.view())

        init_users()
        init_credentials()

        self._username = ft.TextField(
            label="Username",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
            hint_text="username",
            **LoginStyle.text_field(),
        )

        self._password = ft.TextField(
            label="Password",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            password=True,
            can_reveal_password=True,
            on_submit=self._on_login,
            **LoginStyle.text_field(),
        )

        self._error_msg = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

        self._login_btn = ft.Button(
            "Sign In",
            on_click=self._on_login,
            **LoginStyle.login_button(),
        )

        self.controls = [
            ft.Container(
                **LoginStyle.card(),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Image(
                                    src="icon.png",
                                    width=96,
                                    height=96,
                                ),
                            ],
                        ),
                        ft.Container(height=8),
                        ft.Text(
                            "Script Orchestration Platform", size=13, color="#7a8fa6"
                        ),
                        ft.Container(height=36),
                        self._username,
                        ft.Container(height=16),
                        self._password,
                        ft.Container(height=6),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            controls=[
                                ft.GestureDetector(
                                    mouse_cursor=ft.MouseCursor.CLICK,
                                    on_tap=self._on_forgot_password,
                                    content=ft.Text(
                                        "Forgot password?",
                                        size=12,
                                        color="#4a90d9",
                                    ),
                                ),
                            ],
                        ),
                        ft.Container(height=10),
                        self._error_msg,
                        ft.Container(height=18),
                        self._login_btn,
                        ft.Container(height=16),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=4,
                            controls=[
                                ft.Text(
                                    "Don't have an account?",
                                    size=12,
                                    color="#7a8fa6",
                                ),
                                ft.GestureDetector(
                                    mouse_cursor=ft.MouseCursor.CLICK,
                                    on_tap=self._on_go_register,
                                    content=ft.Text(
                                        "Register",
                                        size=12,
                                        color="#4a90d9",
                                        weight=ft.FontWeight.W_600,
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
            )
        ]

    async def _on_login(self, e):
        username = self._username.value.strip().lower()
        password = self._password.value

        valid, msg = validate_username(username)
        if not valid:
            self._error_msg.value = msg
            self._error_msg.visible = True
            self._error_msg.update()
            return

        if check_must_change_password(username):
            self._show_change_password_dialog(username)
            return

        user = verify_user(username, password)
        if user:
            self.page.session.store.set("username", user["username"])
            self.page.session.store.set("role", user["role"])
            set_session_password(password)
            set_session_owner(user["username"])
            self._error_msg.value = ""
            self._error_msg.visible = False
            self._error_msg.update()
            await self.page.push_route("/")
        else:
            self._error_msg.value = "Invalid username or password"
            self._error_msg.visible = True
            self._error_msg.update()

    def _on_forgot_password(self, e):
        dlg = ft.AlertDialog(
            title=ft.Text("Reset Password"),
            content=ft.Text(
                "Please contact your administrator to reset your password.",
                size=14,
            ),
            actions=[
                ft.TextButton("OK", on_click=lambda _: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)

    def _show_change_password_dialog(self, username):
        new_pwd = ft.TextField(
            label="New Password",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            password=True,
            can_reveal_password=True,
            width=350,
        )
        confirm_pwd = ft.TextField(
            label="Confirm Password",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            password=True,
            can_reveal_password=True,
            width=350,
        )
        error = ft.Text("", size=12, color="#f85149", visible=False)

        async def on_submit(_):
            if not new_pwd.value or not confirm_pwd.value:
                error.value = "Please fill in both fields"
                error.visible = True
                error.update()
                return

            if new_pwd.value != confirm_pwd.value:
                error.value = "Passwords do not match"
                error.visible = True
                error.update()
                return

            valid, msg = validate_password(new_pwd.value)
            if not valid:
                error.value = msg
                error.visible = True
                error.update()
                return

            change_password(username, new_pwd.value)
            user = verify_user(username, new_pwd.value)
            self.page.session.store.set("username", user["username"])
            self.page.session.store.set("role", user["role"])
            set_session_password(new_pwd.value)
            set_session_owner(user["username"])
            self.page.pop_dialog()
            await self.page.push_route("/")

        dlg = ft.AlertDialog(
            title=ft.Text("Set New Password"),
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Your password has been reset by an administrator. Please set a new password.",
                        size=13,
                    ),
                    ft.Container(height=10),
                    new_pwd,
                    ft.Container(height=8),
                    confirm_pwd,
                    error,
                ],
                spacing=4,
                tight=True,
                width=350,
            ),
            actions=[
                ft.Button("Set Password", on_click=on_submit),
            ],
            modal=True,
        )
        self.page.show_dialog(dlg)

    async def _on_go_register(self, e):
        await self.page.push_route("/register")
