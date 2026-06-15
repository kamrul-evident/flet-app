import flet as ft
import os

from data.flow_registry import FlowRegistry
from utils.config import Config, Style
from utils.credentials_store import list_credentials



class AddFlowModal(ft.AlertDialog):
    def __init__(self, page: ft.Page, flow: dict = None):
        super().__init__(**Style.dialog_style())
        self.edit_flow = flow
        if flow:
            self.title = ft.Row(
                [
                    ft.Icon(ft.Icons.EDIT_ROUNDED, color=Config.SIDEBAR_BG, size=20),
                    ft.Text("Edit Flow", size=16, weight=ft.FontWeight.W_600),
                ],
                spacing=10,
            )

        # self.on_success = on_success
        self.page_ref = page
        # --- Fields ---
        self.name_field = ft.TextField(**Style.name__field_style())
        self.script_path_field = ft.TextField(**Style.script_path__field_style())
        self.schedule_type = ft.Dropdown(
            **Style.dropdown_style(), on_select=self.handle_dropdown_select
        )

        self.interval_field = ft.TextField(**Style.interval_field_style())

        # --- Credentials multi-select ---
        owner = page.session.store.get("username")
        self._credentials = list_credentials(owner) if owner else []
        self._credential_checks: dict[int, ft.Checkbox] = {}

        if self._credentials:
            cred_controls = []
            for c in self._credentials:
                cb = ft.Checkbox(label=c["name"], value=False)
                self._credential_checks[c["id"]] = cb
                cred_controls.append(cb)
            cred_body = ft.Column(
                controls=cred_controls, scroll=ft.ScrollMode.AUTO, tight=True, spacing=0
            )
        else:
            cred_body = ft.Text(
                "No credentials — add one in Credentials tab",
                italic=True,
                size=12,
                color=Config.MUTED,
            )

        self.credentials_section = ft.Column(
            spacing=4,
            controls=[
                ft.Text("Credentials", size=12, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=cred_body,
                    border=ft.Border.all(1, Config.BORDER),
                    border_radius=8,
                    padding=8,
                    height=140,
                ),
            ],
        )

        # --- Pre-fill if editing ---
        if flow:
            self.name_field.value = flow.get("name", "")
            self.script_path_field.value = flow.get("script_path", "")
            self.schedule_type.value = flow.get("schedule_type", "Interval")

            if self.schedule_type.value == "Interval":
                self.interval_field.value = str(flow.get("interval_minutes", "15"))
                self.interval_field.visible = True
            else:
                self.interval_field.visible = False

            # Disable fields that shouldn't change during edit
            self.script_path_field.read_only = True
            self.schedule_type.disabled = True

            for cid in FlowRegistry.get_credential_ids(flow):
                cb = self._credential_checks.get(cid)
                if cb:
                    cb.value = True

        self.content = ft.Column(
            **Style.dialog_content_style(),
            controls=[
                ft.Divider(height=1, color=Config.BORDER),
                ft.Row(
                    [
                        self.name_field,
                    ],
                ),
                ft.Row(
                    [
                        self.script_path_field,
                        ft.IconButton(
                            **Style.file_picker_icon_style(),
                            offset=ft.Offset(0, -0.25),
                            on_click=self._on_pick_click,
                        ),
                    ],
                ),
                ft.Divider(height=1, color=Config.BORDER),
                ft.Row([self.schedule_type]),
                ft.Row([self.interval_field]),
                self.credentials_section,
            ],
        )

        self.actions = [
            ft.Button(
                **Style.dialog_cancel_button_style(),
                on_click=lambda e: page.pop_dialog(),
            ),
            ft.Button(
                **Style.dialog_save_button_style(),
                content="Update Flow" if flow else "Save Flow",
                on_click=self._on_save,
            ),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def _on_file_result(self, e):
        if e.files:
            self.script_path_field.value = e.files[0].path
            self.update()

    def handle_dropdown_select(self, e: ft.Event[ft.Dropdown]):
        is_continuous = e.control.value == "Continuous"
        self.interval_field.visible = not is_continuous

        self.update()

    # ── Pick file handler (async) ───────────────────────────────────
    async def _on_pick_click(self):
        result = await self.page_ref.file_picker.pick_files(  # noqa
            dialog_title="Choose your Python script",
            allowed_extensions=["py"],
            allow_multiple=False,
            initial_directory=os.getcwd(),
        )

        if result and len(result) > 0:
            path = result[0].path
            self.script_path_field.value = path

    def _on_save(self, e):
        name = self.name_field.value
        path = self.script_path_field.value

        self.name_field.error = None
        self.script_path_field.error = None

        if not name:
            self.name_field.error = "Name is required"
            return

        # Check for unique name
        all_flows = FlowRegistry.get_all_flows()
        for flow in all_flows:
            if flow["name"].lower() == name.lower():
                # If adding new, any match is a duplicate
                # If editing, a match is only a duplicate if IDs are different
                if not self.edit_flow or (
                    self.edit_flow and flow["id"] != self.edit_flow["id"]
                ):
                    self.name_field.error = "A flow with this name already exists"
                    return

        if not path:
            self.script_path_field.error = "Path is required"
            return

        script_path = self.script_path_field.value

        credential_ids = [
            cid for cid, cb in self._credential_checks.items() if cb.value
        ]

        flow_config: dict = {
            "name": self.name_field.value,
            "script_path": script_path,
            "schedule_type": self.schedule_type.value,
            "enabled": True,
            "params": {},
            "credential_ids": credential_ids,
        }

        if not self.edit_flow:
            flow_config["owner"] = self.page_ref.session.store.get("username")

        if self.schedule_type.value == "Interval":
            # Guard: clamp interval between 1 and 10,080 (1 week in minutes)
            try:
                interval = int(self.interval_field.value)
                interval = max(1, min(interval, 10080))
            except (ValueError, TypeError):
                interval = 15
            flow_config["interval_minutes"] = interval

        e.control.page.pop_dialog()

        if self.edit_flow:
            FlowRegistry.update_flow(self.edit_flow["id"], flow_config)

        else:
            FlowRegistry.add_flow(flow_config)
