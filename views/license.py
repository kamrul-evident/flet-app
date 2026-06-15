import flet as ft
from utils import LoginStyle
from utils.hwid import get_hwid_display
from utils.license_validator import activate_license, get_trial_info


class LicenseView(ft.View):
    def __init__(self, page: ft.Page):
        super().__init__(**LoginStyle.view())

        hwid = get_hwid_display()

        # Check if trial has expired to show a message
        trial_info = get_trial_info()
        trial_expired = trial_info is None  # None means no trial or expired

        self._hwid_field = ft.TextField(
            value=hwid,
            read_only=True,
            multiline=True,
            min_lines=3,
            text_size=12,
            **LoginStyle.text_field(),
        )

        self._key_field = ft.TextField(
            label="License Key",
            hint_text="Paste your DRYX-... key here",
            prefix_icon=ft.Icons.VPN_KEY_OUTLINED,
            multiline=True,
            min_lines=3,
            max_lines=5,
            text_size=12,
            **LoginStyle.text_field(),
        )

        self._status_msg = ft.Text("", size=13, visible=False)

        self._activate_btn = ft.Button(
            "Activate",
            on_click=self._on_activate,
            **LoginStyle.login_button(),
        )

        self.controls = [
            ft.Container(
                **LoginStyle.card(),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
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
                        ft.Text("License Activation", size=13, color="#7a8fa6"),
                        ft.Text(
                            "Your trial has expired. Please activate a license to continue.",
                            size=12,
                            color="#f85149",
                            visible=trial_expired,
                        ),
                        ft.Container(height=20),
                        ft.Text(
                            "Your Hardware ID:",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color="#ffffff",
                        ),
                        ft.Stack(
                            [
                                ft.Row(
                                    [
                                        self._hwid_field,
                                    ]
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.COPY,
                                    tooltip="Copy to clipboard",
                                    on_click=self._copy_hwid,
                                    bottom=2,
                                    right=2,
                                ),
                            ]
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    "Send this ID to your vendor to receive a license key.",
                                    size=11,
                                    color="#7a8fa6",
                                ),
                            ],
                            expand=True,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        self._key_field,
                        ft.Container(height=18),
                        self._activate_btn,
                        ft.Container(height=10),
                        self._status_msg,
                    ],
                ),
            )
        ]

    async def _copy_hwid(self):
        await ft.Clipboard().set(self._hwid_field.value)

    async def _on_activate(self, e):
        key = self._key_field.value.strip()

        if not key:
            self._status_msg.value = "Please paste your license key"
            self._status_msg.color = "#f85149"
            self._status_msg.visible = True
            self._status_msg.update()
            return

        success, message = activate_license(key)

        if success:
            self._status_msg.value = "License activated!"
            self._status_msg.color = "#3fb950"
            self._status_msg.visible = True
            self._status_msg.update()
            await self.page.push_route("/login")
        else:
            self._status_msg.value = message
            self._status_msg.color = "#f85149"
            self._status_msg.visible = True
            self._status_msg.update()
