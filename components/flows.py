import flet as ft
import asyncio
from data.flow_registry import FlowRegistry
from .add_flow_modal import AddFlowModal
from utils.flow_engine import engine
from utils.license_validator import get_license_info
from datetime import datetime
from utils.config import Style


class Flows(ft.Column):
    def __init__(
        self,
        page: ft.Page,
    ):
        super().__init__(expand=True)
        self.flows = []
        self.ref_page = page
        self.running = False
        self.search_field = ft.TextField(
            **Style.search_field_params(), on_change=self._on_search_change
        )

        self.header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("Deployed Flows", size=22, weight=ft.FontWeight.BOLD),
                ft.Row(
                    controls=[
                        ft.Container(
                            **Style.search_container_style(),
                            content=self.search_field,
                        ),
                        ft.IconButton(
                            **Style.add_flow_style(),
                            on_click=self._on_add_click,
                        ),
                        ft.IconButton(
                            **Style.refresh_style(),
                            on_click=lambda _: self.load_flows(),
                        ),
                    ],
                    spacing=5,
                ),
            ],
        )

        # Data Table
        self.flows = FlowRegistry.get_flows_for(
            self._current_owner(), self._is_admin()
        )
        self.flows_list = ft.ListView(
            expand=True,
            spacing=0,
            controls=[FlowRow(flow, self) for flow in self.flows],
        )

        self.flows_table = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                # Header Row
                ft.Container(**Style.header_style()),
                self.flows_list,
            ],
        )

        self.controls = [
            self.header,
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),  # Spacing
            ft.Container(
                **Style.flows_table_style(),
                content=self.flows_table,
            ),
        ]

    def did_mount(self):
        self.running = True
        self.page.run_task(self._poll_updates)

    def will_unmount(self):
        self.running = False

    async def _poll_updates(self):
        while self.running:
            try:
                self.load_flows()
            except Exception as e:
                print(f"Error in UI poll: {e}")
            await asyncio.sleep(2)

    def _current_owner(self) -> str | None:
        return self.ref_page.session.store.get("username")

    def _is_admin(self) -> bool:
        return self.ref_page.session.store.get("role") == "admin_role"

    def load_flows(self):
        self.flows = FlowRegistry.get_flows_for(
            self._current_owner(), self._is_admin()
        )
        search_query = (
            self.search_field.value.lower() if self.search_field.value else ""
        )

        # Keep track of existing rows by flow id
        existing_rows = {row.flow["id"]: row for row in self.flows_list.controls}  # noqa
        new_controls = []

        for flow in self.flows:
            flow_id = flow["id"]
            flow_name = flow.get("name", "").lower()

            # Visibility filter
            visible = True
            if search_query and search_query not in flow_name:
                visible = False

            if flow_id in existing_rows:
                # Update an existing row
                row = existing_rows[flow_id]
                row.update_flow_data(flow)  # noqa
                row.visible = visible
                new_controls.append(row)
            else:
                # Add a new row
                row = FlowRow(flow, self)
                row.visible = visible
                new_controls.append(row)

        self.flows_list.controls = new_controls

        if self.page:
            self.update()

    def _on_search_change(self, e):
        self.load_flows()

    def _on_add_click(self, e):
        info = get_license_info()
        max_flows = info.get("max_flows") if info else 0
        tier_name = info.get("tier", "Trial") if info else "Trial"

        # License cap applies to total flows on the machine, not per-user visible ones
        total_flows = len(FlowRegistry.get_all_flows())

        if max_flows is not None and total_flows >= max_flows:
            dlg = ft.AlertDialog(
                title=ft.Text("Flow Limit Reached"),
                content=ft.Text(
                    f"Your {tier_name} plan allows only {max_flows} flows. "
                    f"Please delete some of your old flows or upgrade your plan."
                ),
                actions=[
                    ft.TextButton("OK", on_click=lambda _: self.page.pop_dialog()),
                ],
            )
            self.page.show_dialog(dlg)
            return

        modal = AddFlowModal(self.page)
        self.page.show_dialog(modal)


class FlowRow(ft.Column):
    def __init__(self, flow, flows_parent):
        super().__init__(spacing=0)
        self.flow = flow
        self.flows_parent = flows_parent

        flow_id_full = flow["id"]
        flow_id_short = flow_id_full[:8]
        name = flow.get("name", "Unknown")
        status = flow.get("status", "IDLE")
        last_run = flow.get("last_run", "Never")

        status_color = (
            ft.Colors.GREEN
            if status == "RUNNING"
            else (ft.Colors.RED if status == "ERROR" else ft.Colors.ON_SURFACE_VARIANT)
        )

        if last_run and last_run != "Never":
            try:
                dt = datetime.fromisoformat(last_run)
                last_run_display = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                last_run_display = str(last_run)
        else:
            last_run_display = "Never"

        interval = (
            flow.get("interval_minutes", "-")
            if flow.get("schedule_type") == "Interval"
            else "-"
        )

        self.interval_label = ft.Text(str(interval), width=100)

        self.expand_icon = ft.Icon(
            **Style.flow_expand_icon_style(),
        )

        self.run_button = ft.IconButton(
            **Style.run_icon_style(),
            on_click=self._on_run_once,
            visible=status != "RUNNING",
            disabled=not flow.get("enabled", True),
        )
        self.enabled_switch = ft.Switch(
            value=flow.get("enabled", True),
            on_change=self._on_toggle_enabled,
            scale=0.6,
        )

        self.run_progress = ft.Container(
            content=ft.ProgressRing(width=16, height=16, stroke_width=2),
            padding=ft.Padding.all(14),
            visible=status == "RUNNING",
        )

        self.edit_button = ft.IconButton(
            **Style.edit_flow_style(), on_click=self.edit_flow
        )

        self.name_label = ft.Text(name, expand=True)
        self.main_row = ft.Container(
            **Style.flow_row_container_style(),
            content=ft.Row(
                controls=[
                    ft.GestureDetector(
                        mouse_cursor=ft.MouseCursor.CLICK,
                        on_tap=self.toggle_history,
                        content=ft.Container(
                            width=40,
                            content=ft.Container(
                                **Style.expand_icon_style(),
                                content=self.expand_icon,
                            ),
                        ),
                    ),
                    ft.Container(
                        width=60,
                        content=self.enabled_switch,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Text(flow_id_short, width=100, tooltip=flow_id_full),
                    self.name_label,
                    self.interval_label,
                    ft.Container(
                        width=100,
                        content=ft.Text(
                            status,
                            **Style.flow_status_style(status_color),
                        ),
                    ),
                    ft.Text(last_run_display, width=130, size=12),
                    ft.Container(
                        width=120,
                        content=ft.Row(
                            controls=[
                                self.run_button,
                                self.run_progress,
                                ft.IconButton(
                                    **Style.edit_flow_style(),
                                    on_click=self.edit_flow,
                                ),
                                ft.IconButton(
                                    **Style.delete_icon_style(),
                                    on_click=self._on_delete,
                                ),
                            ],
                            spacing=0,
                        ),
                    ),
                ]
            ),
        )

        self.history_list = ft.ListView(**Style.history_list_style())
        self.history_container = ft.Container(
            **Style.history_container_style(),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Execution History", weight=ft.FontWeight.BOLD, size=14
                            ),
                            ft.TextButton(
                                "Clear",
                                icon=ft.Icons.DELETE_SWEEP,
                                style=ft.ButtonStyle(color=ft.Colors.ERROR),
                                on_click=self._on_clear_history,
                                height=30,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(
                        **Style.history_header_row_style(),
                        content=ft.Row(controls=Style.build_history_labels()),
                    ),
                    self.history_list,
                ]
            ),
        )

        self.controls = [self.main_row, self.history_container]

    def update_flow_data(self, new_flow):
        # Check if anything changed before updating to avoid unnecessary UI redraws
        old_status = self.flow.get("status")
        new_status = new_flow.get("status", "IDLE")
        old_last_run = self.flow.get("last_run")
        new_last_run = new_flow.get("last_run", "Never")
        old_name = self.flow.get("name")
        new_name = new_flow.get("name")
        old_interval = self.flow.get("interval_minutes")
        new_interval = new_flow.get("interval_minutes")

        self.flow = new_flow

        if (
            old_status != new_status
            or old_last_run != new_last_run
            or old_name != new_name
            or old_interval != new_interval
        ):
            status_color = (
                ft.Colors.GREEN
                if new_status == "RUNNING"
                else (
                    ft.Colors.RED
                    if new_status == "ERROR"
                    else ft.Colors.ON_SURFACE_VARIANT
                )
            )

            if new_last_run and new_last_run != "Never":
                try:
                    dt = datetime.fromisoformat(new_last_run)
                    last_run_display = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    last_run_display = str(new_last_run)
            else:
                last_run_display = "Never"

            # Update the text controls inside the main_row
            self.enabled_switch.value = new_flow.get("enabled", True)
            self.name_label.value = new_name
            self.interval_label.value = str(
                new_flow.get("interval_minutes", "-")
                if new_flow.get("schedule_type") == "Interval"
                else "-"
            )

            status_container = self.main_row.content.controls[5]  # noqa
            status_text = status_container.content
            status_text.value = new_status
            status_text.color = status_color

            last_run_text = self.main_row.content.controls[6]  # noqa
            last_run_text.value = last_run_display

            if new_status == "RUNNING":
                self.run_button.visible = False
                self.run_progress.visible = True
            else:
                self.run_button.visible = True
                self.run_button.disabled = not new_flow.get("enabled", True)
                self.run_progress.visible = False

            # Auto-update history if expanded and the state just changed
            if self.history_container.visible and old_status != new_status:
                self.load_history()
            else:
                self.update()

    def toggle_history(self, e):
        self.history_container.visible = not self.history_container.visible
        self.expand_icon.name = (
            ft.Icons.KEYBOARD_ARROW_DOWN
            if self.history_container.visible
            else ft.Icons.CHEVRON_RIGHT
        )
        if self.history_container.visible:
            self.load_history()
        self.update()

    def load_history(self):
        executions = FlowRegistry.get_executions(self.flow["id"])
        # Sort by timestamp descending
        executions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        self.history_list.controls.clear()

        if not executions:
            self.history_list.controls.append(
                ft.Text("No execution history found.", size=12, italic=True)
            )

        for exec_data in executions:
            exec_id = exec_data.get("id", "")[:8]
            timestamp_str = exec_data.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(timestamp_str)
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                timestamp = timestamp_str

            duration = exec_data.get("duration", "N/A")
            status = exec_data.get("status", "Unknown")
            status_color = (
                ft.Colors.GREEN
                if status == "Success"
                else ft.Colors.RED
                if status == "Failed"
                else ft.Colors.ON_SURFACE_VARIANT
            )

            row = ft.Container(
                **Style.history_row_container_style(),
                content=ft.Row(
                    controls=[
                        ft.Text(exec_id, width=100, size=12),
                        ft.Text(timestamp, width=150, size=12),
                        ft.Text(duration, width=100, size=12),
                        ft.Text(status, width=80, size=12, color=status_color),
                        ft.Container(
                            expand=True,
                            content=ft.TextButton(
                                "View Logs",
                                icon=ft.Icons.RECEIPT_LONG,
                                style=ft.ButtonStyle(padding=0),
                                height=25,
                                on_click=lambda e, logs=exec_data.get("logs", "No logs."): (
                                    self.show_logs(logs)
                                ),
                            ),
                        ),
                    ]
                ),
            )
            self.history_list.controls.append(row)

        self.update()

    def show_logs(self, logs):
        def close_dlg(e):
            dlg.open = False
            self.page.update()

        def on_dismiss(e):
            # Clean up: remove the dialog from the overlay when dismissed
            if dlg in self.page.overlay:
                self.page.overlay.remove(dlg)
            self.page.update()

        dlg = ft.AlertDialog(
            **Style.logs_dialog_style(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.TextField(
                                value=logs,
                                multiline=True,
                                read_only=True,
                                border=ft.InputBorder.NONE,
                                text_size=12,
                                expand=True,
                            )
                        ],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    **Style.logs_container_style(),
                )
            ),
            actions=[ft.TextButton("Close", on_click=close_dlg)],
            on_dismiss=on_dismiss,
        )

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _on_run_once(self, e):
        flow_id = self.flow["id"]
        flow = FlowRegistry.get_flow(flow_id)
        if flow:
            self.run_button.visible = False
            self.run_progress.visible = True
            self.update()
            engine.trigger_flow(flow)

    def _on_delete(self, e):
        flow_id = self.flow["id"]
        if FlowRegistry.delete_flow(flow_id):
            self.flows_parent.load_flows()
            self.flows_parent.page.snack_bar = ft.SnackBar(
                content=ft.Text("Flow deleted successfully")
            )
            self.flows_parent.page.snack_bar.open = True
            self.flows_parent.page.update()

    def _on_clear_history(self, e):
        flow_id = self.flow["id"]
        FlowRegistry.clear_executions(flow_id)
        self.load_history()

    def edit_flow(self, e):
        modal = AddFlowModal(self.flows_parent.page, flow=self.flow)
        self.page.show_dialog(modal)

    def _on_toggle_enabled(self, e):
        enabled = self.enabled_switch.value
        FlowRegistry.update_flow(self.flow["id"], {"enabled": enabled})

        if not enabled:
            # If disabled, ensure it stops if running
            engine.stop_flow(self.flow["id"])

            # Immediate UI Update to show it's stopping/stopped
            self.run_button.visible = True
            self.run_button.disabled = True
            self.run_progress.visible = False

            status_container = self.main_row.content.controls[6]
            status_text = status_container.content
            status_text.value = "ABORTED"
            status_text.color = ft.Colors.ON_SURFACE_VARIANT
        else:
            self.run_button.disabled = False

        self.update()
