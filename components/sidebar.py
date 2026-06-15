import flet as ft
from utils import Config


class SidebarItem(ft.Container):
    def __init__(self, icon, text, is_active=False, on_click=None):
        super().__init__()
        self._is_active = is_active
        self.padding = ft.Padding.symmetric(horizontal=15, vertical=10)
        self.border_radius = 8
        self._icon = icon
        self._text = text
        self.on_click = on_click
        self.on_hover = self.hover_changed
        # Internal controls we need to update when state changes
        self.icon_ctl = ft.Icon(icon, size=20)
        self.text_ctl = ft.Text(value=text, size=14)

        self.content = ft.Row(controls=[self.icon_ctl, self.text_ctl], spacing=15)
        self._update_style()

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value: bool):
        self._is_active = value
        self._update_style()
        self.update()

    def _update_style(self):
        self.bgcolor = Config.SIDEBAR_ACTIVE if self._is_active else None
        self.icon_ctl.name = self._icon
        self.icon_ctl.color = ft.Colors.WHITE if self._is_active else ft.Colors.WHITE_70
        self.text_ctl.value = self._text
        self.text_ctl.color = ft.Colors.WHITE if self._is_active else ft.Colors.WHITE_70
        self.text_ctl.weight = (
            ft.FontWeight.W_500 if self._is_active else ft.FontWeight.NORMAL
        )

    def hover_changed(self, e):
        if not self._is_active:
            e.control.bgcolor = Config.SIDEBAR_HOVER if e.data == "true" else None
            e.control.update()
