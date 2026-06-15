import sys
import os
from utils import db2_bootstrap

# Initialize DB2 clidriver for the main process
db2_bootstrap.register()

from routes import RouteHandler
from utils.flow_engine import engine
from utils.license_validator import check_license, start_trial, _get_trial_path
import flet as ft


async def main(page: ft.Page):
    router = RouteHandler(page)
    page.file_picker = ft.FilePicker()
    page.on_route_change = router.route
    page.on_view_pop = router.view_pop
    page.window.always_on_top = True
    page.theme_mode = ft.ThemeMode.LIGHT

    # Validate license (checks paid license first, then active trial)
    is_valid, error_msg = check_license()

    if is_valid:
        # License or trial valid — start engine and go to the login
        engine.start()
        await page.push_route("/login")
    elif not os.path.exists(_get_trial_path()):
        # First launch ever — auto-start 30-day trial
        start_trial()
        engine.start()
        await page.push_route("/login")
    else:
        # Trial an expired or license invalid — show activation screen
        await page.push_route("/license")


ft.run(main)
