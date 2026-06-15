import flet as ft
from utils import LoginStyle
from utils.auth import init_users, add_user, verify_user, validate_password, validate_username
from utils.session import set_session_password, set_session_owner


class RegisterView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__(**LoginStyle.view())

        init_users()

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
            **LoginStyle.text_field(),
        )

        self._confirm_password = ft.TextField(
            label="Confirm Password",
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            password=True,
            can_reveal_password=True,
            **LoginStyle.text_field(),
        )

        self._error_msg = ft.Text("", color=ft.Colors.ERROR, size=13, visible=False)

        self._register_btn = ft.Button(
            "Create Account",
            on_click=self._on_register,
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
                            "Create your account", size=13, color="#7a8fa6"
                        ),
                        ft.Container(height=36),
                        self._username,
                        ft.Container(height=16),
                        self._password,
                        ft.Container(height=16),
                        self._confirm_password,
                        ft.Container(height=10),
                        self._error_msg,
                        ft.Container(height=18),
                        self._register_btn,
                        ft.Container(height=16),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=4,
                            controls=[
                                ft.Text(
                                    "Already have an account?",
                                    size=12,
                                    color="#7a8fa6",
                                ),
                                ft.GestureDetector(
                                    mouse_cursor=ft.MouseCursor.CLICK,
                                    on_tap=self._on_go_login,
                                    content=ft.Text(
                                        "Sign In",
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

    async def _on_register(self, e):
        # TODO: implement registration logic
        username = self._username.value.strip().lower()
        password = self._password.value
        confirm = self._confirm_password.value

        if not username or not password:
            self._error_msg.value = "Please fill in all fields"
            self._error_msg.visible = True
            self._error_msg.update()
            return

        valid, msg = validate_username(username)
        if not valid:
            self._error_msg.value = msg
            self._error_msg.visible = True
            self._error_msg.update()
            return

        if password != confirm:
            self._error_msg.value = "Passwords do not match"
            self._error_msg.visible = True
            self._error_msg.update()
            return

        valid, msg = validate_password(password)
        if not valid:
            self._error_msg.value = msg
            self._error_msg.visible = True
            self._error_msg.update()
            return

        success, message = add_user(username, password)
        if not success:
            self._error_msg.value = "This username is already taken. Please sign in or choose another."
            self._error_msg.visible = True
            self._error_msg.update()
            return

        user = verify_user(username, password)
        self.page.session.store.set("username", user["username"])
        self.page.session.store.set("role", user["role"])
        set_session_password(password)
        set_session_owner(user["username"])
        await self.page.push_route("/")

    async def _on_go_login(self, e):
        await self.page.push_route("/login")
