import flet as ft

from views import HomeView, LicenseView, LoginView, RegisterView


class RouteHandler:
    def __init__(self, page: ft.Page):
        self.page = page

    async def route(self, e=None):
        """Called directly on the startup or passed to page.on_route_change."""
        self.page.views.clear()
        match self.page.route:
            case "/":
                active_home_item = await ft.SharedPreferences().get("active_home_item")
                if not active_home_item:
                    active_home_item = "Flows"
                self.page.views.append(
                    HomeView(page=self.page, active_item=active_home_item)
                )

            case "/login":
                self.page.views.append(LoginView(page=self.page))

            case "/register":
                self.page.views.append(RegisterView(page=self.page))

            case "/license":
                self.page.views.append(LicenseView(page=self.page))

            case _:
                pass

        self.page.update()

    async def view_pop(self, e):
        """Called by page.on_view_pop. Must be async in Flet 0.81+."""
        if e.view is not None:
            self.page.views.remove(e.view)
        top_view = self.page.views[-1]
        await self.page.push_route(top_view.route)
