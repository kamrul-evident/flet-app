import sys
import subprocess
import asyncio
import os
import shutil


def _find_bundled_site_packages():
    """
    Finds the site-packages directory bundled by flet build or PyInstaller.
    Returns the absolute path or None if not found.
    """
    candidates = set()

    # 1. Check sys.path (most reliable for Flet build)
    for p in sys.path:
        if "site-packages" in p:
            candidates.add(p)

    # 2. Check PyInstaller _MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.add(os.path.join(meipass, "site-packages"))

    # 3. Fallback: next to executable (Windows Flet build)
    app_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates.add(os.path.join(app_dir, "site-packages"))
    candidates.add(os.path.join(app_dir, "lib", "site-packages"))

    # 4. Fallback: Check Flet's exact build layout from CWD or sys.path
    if sys.platform != "win32":
        # On Linux, Flet bundles things into a specific directory structure
        # Let's see if we can derive the build root from any sys.path entry
        for p in sys.path:
            # Look for the build root if the path contains 'build/linux'
            if "build/linux" in p:
                parts = p.split("build/linux")
                build_linux_path = parts[0] + "build/linux"
                candidates.add(os.path.join(build_linux_path, "site-packages"))

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate

    return None


def _find_cli_binary(cli_name):
    """
    Resolves the absolute path to a CLI binary (duckdb or polars).

    Search order:
    1. Bundled location inside site-packages/ (for built apps)
       - duckdb: site-packages/duckdb_cli/duckdb[.exe]
       - polars: site-packages/Scripts/polars[.exe] (Windows) or site-packages/bin/polars (Linux)
    2. Virtual Environment (sys.prefix) directly
    3. System PATH via shutil.which (blocked if trying to swap to global tool in built app context)
    """
    exe_suffix = ".exe" if sys.platform == "win32" else ""

    # 1. Check bundled site-packages
    sp = _find_bundled_site_packages()
    if sp:
        if cli_name == "duckdb":
            bundled = os.path.join(sp, "duckdb_cli", f"duckdb{exe_suffix}")
        elif cli_name == "polars":
            # On Windows, PIP traditionally puts scripts in Scripts/, on Linux in bin/
            script_dir = "Scripts" if sys.platform == "win32" else "bin"
            bundled = os.path.join(sp, script_dir, f"polars{exe_suffix}")

            # Since Flet might reorganize things during the build, also fallback to 'bin' on Windows just in case
            if not os.path.isfile(bundled) and sys.platform == "win32":
                alt_bundled = os.path.join(sp, "bin", f"polars{exe_suffix}")
                if os.path.isfile(alt_bundled):
                    bundled = alt_bundled
        else:
            bundled = None

        if bundled and os.path.isfile(bundled):
            return bundled

    # 1.5 Check bundled python runtime (the standalone embedded engine)
    from utils.flow_executor import FlowExecutor
    bundled_python = FlowExecutor._find_bundled_python()
    if bundled_python:
        runtime_dir = os.path.dirname(bundled_python)
        
        # Bypass Python pip wrapper for DuckDB to prevent console collapse, hit fat binary directly
        if cli_name == "duckdb":
            real_duckdb = os.path.join(runtime_dir, "Lib", "site-packages", "duckdb_cli", f"duckdb{exe_suffix}")
            if os.path.isfile(real_duckdb):
                return real_duckdb
                
        bundled_scripts = os.path.join(runtime_dir, "Scripts" if sys.platform == "win32" else "bin")
        standalone = os.path.join(bundled_scripts, f"{cli_name}{exe_suffix}")
        if os.path.isfile(standalone):
            return standalone

    # 2. Check Virtual Environment Scripts/bin directly (For Dev Mode)
    script_dir = "Scripts" if sys.platform == "win32" else "bin"
    venv_binary = os.path.join(sys.prefix, script_dir, f"{cli_name}{exe_suffix}")
    if os.path.isfile(venv_binary):
        return venv_binary

    # 3. Fallback: system PATH (shutil.which)
    found = shutil.which(cli_name)  # noqa
    if found:
        # Check if the found binary is effectively local to this project
        found_abs = os.path.abspath(found)
        app_dir = os.path.abspath(os.path.dirname(sys.executable))
        prefix_dir = os.path.abspath(sys.prefix)
        cwd = os.path.abspath(os.getcwd())

        is_local = (
            found_abs.startswith(app_dir)
            or found_abs.startswith(prefix_dir)
            or found_abs.startswith(cwd)
        )

        if is_local:
            return found_abs
        else:
            # Prevent swapping to a conflicting global installation in a dev OR built context.
            return None

    return None


async def _launch_cli_async(cli_name, on_exit_callback=None, binary_override=None):
    """
    Launches a CLI tool in a new, native OS terminal window asynchronously.
    Resolves the absolute path to the binary before launching.
    Executes the `on_exit_callback` when the process terminates.
    """
    binary = binary_override or _find_cli_binary(cli_name)
    if not binary:
        if on_exit_callback:
            on_exit_callback()
        return

    cmd = []

    # If it is a python, we MUST uniquely identify it so we can kill it later without
    # accidentally slaughtering the whole Flet backend!
    unix_exec_binary = (
        f'exec -a FLET_PYTHON_CLI_PROC "{binary}"'
        if cli_name == "python"
        else f'"{binary}"'
    )

    if sys.platform == "win32":
        # Launching with CREATE_NEW_CONSOLE natively creates the isolated console
        # without cmd.exe or start tricks, allowing us to keep track of the PID securely.
        cmd = [binary]
    elif sys.platform == "darwin":
        # AppleScript to open Terminal and run the binary
        cmd = [
            "osascript",
            "-e",
            f'tell app "Terminal" to do script "bash -c \\"{unix_exec_binary}\\""',
        ]
    else:
        # Linux: find a terminal emulator
        # Prioritize specific ones over generic wrapper to ensure correct flags
        terminals = [
            "gnome-terminal",
            "konsole",
            "xfce4-terminal",
            "x-terminal-emulator",
            "xterm",
        ]
        term = None
        for t in terminals:
            if shutil.which(t):  # noqa
                term = t
                break

        if term == "gnome-terminal":
            cmd = [term, "--wait", "--", "bash", "-c", unix_exec_binary]
        elif term == "konsole":
            cmd = [term, "--noclose", "-e", "bash", "-c", unix_exec_binary]
        elif term == "xfce4-terminal":
            cmd = [term, "--disable-server", "-e", "bash", "-c", unix_exec_binary]
        elif term:
            cmd = [term, "-e", "bash", "-c", unix_exec_binary]
        else:
            cmd = ["xterm", "-e", "bash", "-c", unix_exec_binary]  # Fallback

    try:
        # Flet bundles its own libstdc++ and modifies LD_LIBRARY_PATH
        # standalone binaries (and gnome-terminal) WILL crash if they inherit this.
        clean_env = os.environ.copy()
        for key in [
            "LD_LIBRARY_PATH",
            "PYTHONHOME",
            "PYTHONPATH",
            "PYTHONNOUSERSITE",
            "_MEIPASS",
            "_MEIPASS2",
        ]:
            clean_env.pop(key, None)

        if sys.platform == "win32":

            def run_and_wait():
                try:
                    p = subprocess.Popen(  # noqa
                        cmd,
                        env=clean_env,
                        creationflags=subprocess.CREATE_NEW_CONSOLE,
                        close_fds=True,
                    )
                    _win32_processes[cli_name] = p  # noqa
                    p.wait()
                except Exception as e:
                    print(f"Error in Popen thread: {e}")
                finally:
                    _win32_processes.pop(cli_name, None)  # noqa

            # Run in a separate thread so it doesn't freeze the Flet asyncio event loop
            await asyncio.to_thread(run_and_wait)
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=clean_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            async def wait_for_process_exit():
                await process.wait()

            async def poll_binary_death():
                # On Unix, python is launched under the alias 'FLET_PYTHON_CLI_PROC'
                bin_name = (
                    "FLET_PYTHON_CLI_PROC"
                    if cli_name == "python"
                    else os.path.basename(binary)
                )
                # Give the process a moment to actually spawn before polling
                await asyncio.sleep(2.0)

                while True:
                    await asyncio.sleep(1.0)
                    try:
                        if cli_name == "python":
                            # Must use -f to match process arguments since exec -a changes argv[0] but not kernel comm name
                            res = subprocess.run(
                                ["pgrep", "-f", str(bin_name)], capture_output=True
                            )
                        else:
                            # -x ensures we strictly match the process name (e.g. "duckdb")
                            res = subprocess.run(
                                ["pgrep", "-x", str(bin_name)], capture_output=True
                            )
                        if res.returncode != 0:
                            break
                    except Exception:
                        pass

            tasks = [
                asyncio.create_task(wait_for_process_exit()),
                asyncio.create_task(poll_binary_death()),
            ]

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            for p in pending:
                p.cancel()

    except Exception as e:
        print(f"Error launching {cli_name} CLI: {e}")
    finally:
        if on_exit_callback:
            on_exit_callback()


async def launch_duckdb_cli_async(on_exit_callback=None):
    """Launches the DuckDB CLI in a new terminal window."""
    await _launch_cli_async("duckdb", on_exit_callback)


async def launch_polars_cli_async(on_exit_callback=None):
    """Launches the Polars CLI in a new terminal window."""
    await _launch_cli_async("polars", on_exit_callback)


async def launch_python_cli_async(on_exit_callback=None):
    """Launches the Python REPL (bundled only) in a new terminal window."""
    from utils.flow_executor import FlowExecutor

    if not FlowExecutor._is_bundled_app():
        python_exe = sys.executable
    else:
        python_exe = FlowExecutor._find_bundled_python()

    if not python_exe:
        print("Error: Could not find bundled Python interpreter.")
        if on_exit_callback:
            on_exit_callback()
        return

    await _launch_cli_async("python", on_exit_callback, binary_override=python_exe)


async def kill_cli_async(cli_name, binary_override=None):
    """
    Attempts to forcefully kill the given CLI process so the terminal closes.
    This acts as a toggle button handler.
    """
    if sys.platform == "win32":
        # Windows native state-driven termination avoids all process-name collision risks.
        p = _win32_processes.get(cli_name)  # noqa
        if p:
            try:
                p.terminate()
            except Exception:
                pass
        return

    # For Unix, we securely alias Python to avoid slaughtering the backend
    if cli_name == "python" and sys.platform != "win32":
        subprocess.run(
            ["pkill", "-f", "FLET_PYTHON_CLI_PROC"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    binary = binary_override or _find_cli_binary(cli_name)
    if not binary:
        return

    try:
        bin_name = os.path.basename(binary)
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/IM", bin_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # -x ensures we kill the exact process by name, preventing accidental kills
            # of wrappers or similar global commands.
            subprocess.run(
                ["pkill", "-x", bin_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        print(f"Error killing {cli_name} CLI: {e}")
