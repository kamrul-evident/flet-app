import flet as ft
import datetime


class Config:
    # ── Colours / constants ────────────────────────────────────────────────────────
    BG = "#0d1117"
    SURFACE = "#161b22"
    BORDER = "#30363d"
    ACCENT = "#58a6ff"
    GREEN = "#3fb950"
    RED = "#f85149"
    YELLOW = "#d29922"
    TEXT = "#e6edf3"
    MUTED = "#8b949e"
    # ── Sidebar Colors ────────────────────────────────────────────────────────────
    SIDEBAR_BG = "#1f2937"
    SIDEBAR_ACTIVE = "#374151"
    SIDEBAR_HOVER = "#4b5563"
    FONT = "Courier New"

    STEP_LABELS = [
        "Extract from source",
        "Split DEBIT / CREDIT",
        "Unique accounts",
        "Filter dimensions",
        "Register in DuckDB",
        "LEFT JOIN",
        "Write log + tracker",
    ]


class Style:
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page

    @staticmethod
    def dialog_style() -> dict:
        return {
            "shape": ft.RoundedRectangleBorder(radius=12),
            "title_padding": ft.Padding.only(left=24, top=20, right=24, bottom=0),
            "content_padding": ft.Padding.symmetric(horizontal=24, vertical=16),
            "title": ft.Row(
                [
                    ft.Icon(
                        ft.Icons.ACCOUNT_TREE_ROUNDED, color=Config.SIDEBAR_BG, size=20
                    ),
                    ft.Text(
                        "Register New Flow",
                        size=16,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
                spacing=10,
            ),
            "actions_padding": ft.Padding.symmetric(horizontal=24, vertical=16),
        }

    @staticmethod
    def name__field_style() -> dict:
        return {
            "label": "Flow Name",
            "hint_text": "e.g. Finance Cleanup",
            "expand": True,
            "height": 70,
            "helper": " ",
        }

    @staticmethod
    def script_path__field_style() -> dict:
        return {
            "label": "Script Path",
            "hint_text": "e.g. /path/to/script.py",
            "expand": True,
            "height": 70,
            "read_only": True,
            "helper": " ",
        }

    @staticmethod
    def dropdown_style() -> dict:
        return {
            "label": "Schedule Type",
            "options": [
                ft.dropdown.Option("Interval"),
                ft.dropdown.Option("Continuous"),
            ],
            "value": "Interval",
            "width": 200,
        }

    @staticmethod
    def interval_field_style() -> dict:
        return {
            "label": "Interval (minutes)",
            "value": "15",
            "keyboard_type": ft.KeyboardType.NUMBER,
            "expand": True,
        }

    @staticmethod
    def dialog_cancel_button_style() -> dict:
        return {
            "content": "Cancel",
            "height": 40,
            "style": ft.ButtonStyle(
                color=Config.TEXT,
                bgcolor={ft.ControlState.DEFAULT: Config.RED},
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            ),
        }

    @staticmethod
    def dialog_save_button_style() -> dict:
        return {
            "icon": ft.Icons.SAVE_ROUNDED,
            "height": 40,
            "style": ft.ButtonStyle(
                bgcolor={ft.ControlState.DEFAULT: Config.SIDEBAR_BG},
                color={ft.ControlState.DEFAULT: "#ffffff"},
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            ),
        }

    @staticmethod
    def dialog_checkbox_style() -> dict:
        return {
            "label": "Copy to managed library (assets/scripts)",
            "value": True,
            "bottom": 0,
        }

    @staticmethod
    def file_picker_icon_style() -> dict:
        return {
            "icon": ft.Icons.FOLDER_SHARP,
            "icon_size": 20,
            "tooltip": "Browse file",
        }

    @staticmethod
    def dialog_content_style() -> dict:
        return {
            "tight": True,
            "spacing": 14,
            "width": 420,
        }

    @staticmethod
    def search_container_style() -> dict:
        return {
            "width": 300,
        }

    @staticmethod
    def search_field_params() -> dict:
        return {
            "hint_text": "Search",
            "prefix_icon": ft.Icons.SEARCH,
            "height": 35,
            "content_padding": ft.Padding.only(left=10, top=0, bottom=0, right=10),
            "border_radius": 8,
            "text_size": 14,
        }

    @staticmethod
    def add_flow_style():
        return {
            "icon": ft.Icons.ADD_OUTLINED,
            "tooltip": "Add New Flow",
            "icon_size": 20,
        }

    @staticmethod
    def refresh_style() -> dict:
        return {
            "icon": ft.Icons.REFRESH_OUTLINED,
            "tooltip": "Force Refresh",
            "icon_size": 20,
        }

    @staticmethod
    def header_style() -> dict:
        return {
            "padding": ft.Padding.symmetric(vertical=10, horizontal=15),
            "border": ft.Border.only(
                bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
            ),
            "content": ft.Row(
                controls=[
                    ft.Container(width=40),  # Spacer for the expanded icon
                    ft.Text("Active", weight=ft.FontWeight.BOLD, width=60),
                    ft.Text("Flow ID", weight=ft.FontWeight.BOLD, width=100),
                    ft.Text("Flow Name", weight=ft.FontWeight.BOLD, expand=True),
                    ft.Text("Interval(min)", weight=ft.FontWeight.BOLD, width=140),
                    ft.Text("Status", weight=ft.FontWeight.BOLD, width=115),
                    ft.Text("Last Run", weight=ft.FontWeight.BOLD, width=140),
                    ft.Text("Actions", weight=ft.FontWeight.BOLD, width=90),
                ]
            ),
        }

    @staticmethod
    def flows_table_style() -> dict:
        return {
            "border": ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            "border_radius": 8,
            "expand": True,
        }

    @staticmethod
    def flow_expand_icon_style() -> dict:
        return {
            "icon": ft.Icons.CHEVRON_RIGHT,
            "size": 18,
            "color": ft.Colors.ON_SURFACE_VARIANT,
        }

    @staticmethod
    def flow_row_container_style() -> dict:
        return {
            "padding": ft.Padding.symmetric(vertical=5, horizontal=15),
            "border": ft.Border.only(
                bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
            ),
        }

    @staticmethod
    def flow_icon_container_style() -> dict:
        return {
            "bgcolor": ft.Colors.SURFACE_CONTAINER_HIGHEST,
            "border_radius": 12,
            "width": 24,
            "height": 24,
            "alignment": ft.Alignment.CENTER,
        }

    @staticmethod
    def flow_status_style(color) -> dict:
        return {
            "color": color,
            "weight": ft.FontWeight.BOLD,
            "size": 12,
        }

    @staticmethod
    def history_list_style() -> dict:
        return {
            "expand": False,
            "spacing": 0,
            "height": 150,
        }

    @staticmethod
    def history_container_style() -> dict:
        return {
            "visible": False,
            "padding": ft.Padding.only(left=50, top=10, bottom=10, right=15),
            "bgcolor": ft.Colors.SURFACE_CONTAINER_LOW,
        }

    @staticmethod
    def history_header_row_style() -> dict:
        return {
            "padding": ft.Padding.symmetric(vertical=5, horizontal=10),
            "border": ft.Border.only(
                bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
            ),
        }

    @staticmethod
    def history_row_container_style() -> dict:
        return {
            "padding": ft.Padding.symmetric(vertical=5, horizontal=10),
            "border": ft.Border.only(
                bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
            ),
        }

    @staticmethod
    def logs_dialog_style(content) -> dict:
        return {
            "title": ft.Text("Execution Logs"),
            "content": content,
            "actions_alignment": ft.MainAxisAlignment.END,
        }

    @staticmethod
    def logs_container_style() -> dict:
        return {
            "width": 600,
            "height": 400,
        }

    @staticmethod
    def expand_icon_style() -> dict:
        return {
            "bgcolor": ft.Colors.SURFACE_CONTAINER_HIGHEST,
            "border_radius": 12,
            "width": 24,
            "height": 24,
            "alignment": ft.Alignment.CENTER,
        }

    @staticmethod
    def build_history_labels():
        return [
            ft.Text(
                "Execution ID",
                weight=ft.FontWeight.BOLD,
                width=100,
                size=12,
            ),
            ft.Text(
                "Timestamp",
                weight=ft.FontWeight.BOLD,
                width=150,
                size=12,
            ),
            ft.Text(
                "Duration",
                weight=ft.FontWeight.BOLD,
                width=100,
                size=12,
            ),
            ft.Text(
                "Status",
                weight=ft.FontWeight.BOLD,
                width=80,
                size=12,
            ),
            ft.Text(
                "Logs",
                weight=ft.FontWeight.BOLD,
                expand=True,
                size=12,
            ),
        ]

    @staticmethod
    def run_icon_style() -> dict:
        return {
            "icon": ft.Icons.PLAY_ARROW_OUTLINED,
            "tooltip": "Run Once",
            "icon_size": 18,
            "icon_color": ft.Colors.GREEN,
        }

    @staticmethod
    def delete_icon_style() -> dict:
        return {
            "icon": ft.Icons.DELETE_OUTLINE,
            "tooltip": "Delete",
            "icon_size": 18,
            "icon_color": ft.Colors.RED,
        }

    @staticmethod
    def edit_flow_style() -> dict:
        return {
            "icon": ft.Icons.EDIT_OUTLINED,
            "tooltip": "Edit Flow",
            "icon_size": 18,
        }


class LoginStyle:
    @staticmethod
    def view() -> dict:
        return {
            "vertical_alignment": ft.MainAxisAlignment.CENTER,
            "horizontal_alignment": ft.CrossAxisAlignment.CENTER,
        }

    @staticmethod
    def card() -> dict:
        return {
            "width": 420,
            "padding": ft.Padding.all(40),
            "border_radius": 16,
            "bgcolor": "#1a2535",
            "border": ft.Border.all(1, "#2e3d50"),
        }

    @staticmethod
    def text_field(width: int = 360) -> dict:
        return {
            "border_radius": 8,
            "expand": True,
            "bgcolor": "#1e2a38",
            "border_color": "#2e3d50",
            "focused_border_color": "#4a90d9",
            "label_style": ft.TextStyle(color="#7a8fa6"),
            "color": "#ffffff",
            "cursor_color": "#4a90d9",
        }

    @staticmethod
    def login_button() -> dict:
        return {
            "width": 360,
            "height": 46,
            "style": ft.ButtonStyle(
                bgcolor="#4a90d9",
                color="#ffffff",
                shape=ft.RoundedRectangleBorder(radius=8),
                text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_600),
            ),
        }
