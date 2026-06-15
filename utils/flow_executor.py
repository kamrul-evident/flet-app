import subprocess
import os
import re
import sys
import shutil
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("flow_engine")


class FlowExecutor:
    @staticmethod
    def _find_bundled_python() -> Optional[str]:
        """
        Looks for a bundled Python interpreter inside the application directory.
        Common locations for flet build / bundled runtimes:
        - python_runtime/python.exe (Embedded)
        - venv/Scripts/python.exe (Windows venv)
        - venv/bin/python (Linux venv)
        """
        app_dir = os.path.dirname(sys.executable)

        candidates = []
        if sys.platform == "win32":
            candidates = [
                os.path.join(app_dir, "python_runtime", "python.exe"),
                os.path.join(app_dir, "venv", "Scripts", "python.exe"),
                os.path.join(app_dir, "python", "python.exe"),
            ]
        else:
            candidates = [
                os.path.join(app_dir, "python_runtime", "bin", "python"),
                os.path.join(app_dir, "venv", "bin", "python"),
                os.path.join(app_dir, "python", "bin", "python"),
            ]

        for candidate in candidates:
            if os.path.isfile(candidate):
                # Basic check to see if it works
                try:
                    subprocess.run(
                        [candidate, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        creationflags=0x08000000 if sys.platform == "win32" else 0,
                    )
                    return candidate
                except Exception:
                    continue
        return None

    @staticmethod
    def _find_system_python() -> str:
        """
        Finds a system Python interpreter that is NOT the bundled app
        and is NOT a Windows Store stub.
        Returns the path to the interpreter, or raises RuntimeError.
        """
        # Directories that belong to the bundled app — any Python found
        # here is the embedded interpreter and must NOT be used.
        bundle_dirs = set()
        if getattr(sys, "_MEIPASS", None):
            bundle_dirs.add(os.path.normcase(os.path.abspath(sys._MEIPASS)))
        if getattr(sys, "frozen", False):
            bundle_dirs.add(
                os.path.normcase(os.path.abspath(os.path.dirname(sys.executable)))
            )
        # For flet build: the app dir itself
        app_dir = os.path.normcase(os.path.abspath(os.path.dirname(sys.executable)))
        bundle_dirs.add(app_dir)

        def _is_valid_python(path: str) -> bool:
            """Return True only if this Python is NOT inside the bundle
            and NOT a Windows Store stub."""
            norm = os.path.normcase(os.path.abspath(path))
            for bd in bundle_dirs:
                if norm.startswith(bd):
                    return False
            if "windowsapps" in norm:
                return False
            return True

        def _verify_python(path: str) -> bool:
            """Verify the interpreter actually works by running --version."""
            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=0x08000000 if sys.platform == "win32" else 0,
                )
                return result.returncode == 0
            except Exception:
                return False

        # ── Strategy 1: Use the Windows "py" launcher (most reliable) ──
        if sys.platform == "win32":
            # Check the known installation location first (doesn't depend on shutil.which,
            # which had bugs on Windows before Python 3.12)
            py = None
            launcher_path = os.path.expandvars(
                r"%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
            )
            if os.path.isfile(launcher_path):
                py = launcher_path

            # Fallback: try shutil.which (wrapped for compatibility)
            if not py:
                try:
                    py = shutil.which("py")
                except (TypeError, ValueError):
                    py = None

            if py and _is_valid_python(py):
                try:
                    result = subprocess.run(
                        [py, "-3", "-c", "import sys; print(sys.executable)"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        creationflags=0x08000000,
                    )
                    if result.returncode == 0:
                        real_python = result.stdout.strip()
                        if real_python and os.path.isfile(real_python):
                            pythonw = os.path.join(
                                os.path.dirname(real_python), "pythonw.exe"
                            )
                            if os.path.isfile(pythonw):
                                return pythonw
                            return real_python
                except Exception:
                    pass

        # ── Strategy 2: Search PATH (filtering stubs and bundle) ──
        for name in ("pythonw", "python", "python3"):
            found = shutil.which(name)
            if found and _is_valid_python(found) and _verify_python(found):
                return found

        # ── Strategy 3: Use uv to find Python (if available) ──
        uv = shutil.which("uv")
        if uv:
            try:
                result = subprocess.run(
                    [uv, "python", "find"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=0x08000000 if sys.platform == "win32" else 0,
                )
                if result.returncode == 0:
                    found = result.stdout.strip()
                    if found and os.path.isfile(found) and _is_valid_python(found):
                        if sys.platform == "win32":
                            pythonw = os.path.join(
                                os.path.dirname(found), "pythonw.exe"
                            )
                            if os.path.isfile(pythonw):
                                return pythonw
                        return found
            except Exception:
                pass

        # ── Strategy 4: Scan common Windows install locations ──
        if sys.platform == "win32":
            for base in [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python"),
                r"C:\Python",
                r"C:\Program Files\Python",
            ]:
                if os.path.isdir(base):
                    for entry in sorted(os.listdir(base), reverse=True):
                        if entry.lower() == "launcher":
                            continue
                        for exe in ("pythonw.exe", "python.exe"):
                            candidate = os.path.join(base, entry, exe)
                            if os.path.isfile(candidate) and _verify_python(candidate):
                                return candidate

        raise RuntimeError(
            "Cannot find a system Python interpreter. "
            "Please ensure Python is installed and available on PATH."
        )

    @staticmethod
    def _is_bundled_app() -> bool:
        """
        Returns True if running as a bundled app (flet build or PyInstaller).
        In a bundled app, sys.executable is NOT a Python interpreter.
        """
        # PyInstaller frozen check
        if getattr(sys, "frozen", False):
            return True
        # Flet build check: sys.executable won't be a python interpreter
        exe_name = os.path.basename(sys.executable).lower()
        return not exe_name.startswith("python")

    @staticmethod
    def _find_bundled_site_packages() -> Optional[str]:
        """
        Finds the site-packages directory bundled by flet build or PyInstaller.
        This allows user scripts to import libraries bundled with the app
        (polars, duckdb, sqlalchemy, etc.) even when using system Python.
        """
        candidates = set()

        # 1. Check sys.path (most reliable for Flet build)
        for p in sys.path:
            if "site-packages" in p:
                candidates.add(p)

        # 2. Check PyInstaller _MEIPASS
        if getattr(sys, '_MEIPASS', None):
            candidates.add(os.path.join(sys._MEIPASS, "site-packages"))

        # 3. Fallback: next to executable (Windows Flet build)
        app_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.add(os.path.join(app_dir, "site-packages"))
        candidates.add(os.path.join(app_dir, "lib", "site-packages"))
        
        # 4. Fallback: Check Flet's exact build layout from CWD or sys.path
        if sys.platform != "win32":
            # On Linux, Flet bundles things into a specific directory structure
            for p in sys.path:
                if 'build/linux' in p:
                    parts = p.split('build/linux')
                    build_linux_path = parts[0] + 'build/linux'
                    candidates.add(os.path.join(build_linux_path, "site-packages"))

        for candidate in candidates:
            if os.path.isdir(candidate):
                return candidate

        return None

    @staticmethod
    def _find_system_site_packages() -> Optional[str]:
        """
        Attempts to find the system's global site-packages to allow
        bundled Python to access user-installed libraries (Hybrid Mode).
        """
        try:
            # Find system python first
            sys_py = FlowExecutor._find_system_python()
            # Ask it where its site-packages are
            result = subprocess.run(
                [sys_py, "-c", "import site; print(site.getsitepackages()[0])"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    @staticmethod
    def _get_subprocess_args(script_path: str) -> list[str]:
        """
        Determines the correct command-line arguments to run a script,
        handling both standard python and bundled (frozen) environments.
        """
        if not FlowExecutor._is_bundled_app():
            # Normal dev environment — sys.executable is a real Python interpreter
            return [sys.executable, "-u", script_path]

        if sys.platform != "win32":
            # Linux/macOS: subprocess with sys.executable works fine,
            # no new GUI window is created on these platforms.
            return [sys.executable, "-u", script_path]

        # ── Windows bundled app ──
        # Must use a separate python.exe to avoid launching a new GUI window.

        # 1. Try bundled venv first (shipped with the app)
        bundled = FlowExecutor._find_bundled_python()
        if bundled:
            logger.info(f"Using bundled Python runtime: {bundled}")
            return [bundled, "-u", script_path]

        # 2. Fallback to system Python if no venv bundled
        python = FlowExecutor._find_system_python()
        logger.info(f"No bundled runtime found. Using system Python: {python}")
        return [python, "-u", script_path]

    @staticmethod
    def _get_creation_flags() -> int:
        if sys.platform == "win32":
            return 0x08000000  # CREATE_NO_WINDOW
        return 0

    @staticmethod
    def _build_database_url(fields: Dict[str, Any]) -> str:
        """Build a SQLAlchemy-compatible URL from decrypted credential fields."""
        from utils.db_url import build_sqlalchemy_url

        return build_sqlalchemy_url(fields["db_type"], fields)

    @staticmethod
    def _sanitize_prefix(name: str) -> str:
        """Turn a credential name into a valid env-var prefix.

        "MSSQL Prod" -> "MSSQL_PROD", "Oracle-Legacy!" -> "ORACLE_LEGACY".
        """
        s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
        if s and s[0].isdigit():
            s = "_" + s
        return s

    @staticmethod
    def _get_clean_env(
        params: Dict[str, Any],
        credentials: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        """
        Returns a clean environment for the subprocess,
        removing Flet-specific variables and adding bundled site-packages
        so user scripts can import libraries bundled with the app.
        """
        import json

        env = os.environ.copy()
        env["FLOW_PARAMS"] = json.dumps(params)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        if credentials:
            seen_prefixes: set[str] = set()
            for name, fields in credentials.items():
                prefix = FlowExecutor._sanitize_prefix(name)
                if not prefix:
                    logger.warning(
                        f"Credential '{name}' produced an empty env-var prefix; skipping."
                    )
                    continue
                if prefix in seen_prefixes:
                    logger.warning(
                        f"Credential '{name}' collides with another on prefix "
                        f"'{prefix}'; the later one overrides the earlier."
                    )
                seen_prefixes.add(prefix)

                env[f"{prefix}_DB_TYPE"] = str(fields.get("db_type", ""))
                env[f"{prefix}_USER"] = str(fields.get("user", ""))
                env[f"{prefix}_PASSWORD"] = str(fields.get("password", ""))
                env[f"{prefix}_HOST"] = str(fields.get("host", ""))
                env[f"{prefix}_PORT"] = str(fields.get("port", ""))
                env[f"{prefix}_DATABASE"] = str(fields.get("database", ""))
                try:
                    env[f"{prefix}_DATABASE_URL"] = FlowExecutor._build_database_url(fields)
                except Exception as e:
                    logger.warning(f"Could not build DATABASE_URL for '{name}': {e}")

        # Remove any inherited Flet-specific variables to prevent
        # child processes from trying to talk to the Flet server.
        flet_vars = [k for k in env.keys() if k.startswith("FLET_")]
        for k in flet_vars:
            del env[k]

        # Remove PyInstaller/bundled-app variables and REPL-triggering variables
        # that would confuse the system Python interpreter or cause infinite REPL loops.
        for var in (
            "PYTHONHOME",
            "_MEIPASS",
            "_MEIPASS2",
            "PYTHONINSPECT",
            "PYTHONSTARTUP",
            "PYTHONNOUSERSITE",
        ):
            env.pop(var, None)

        # ── Setup PYTHONPATH (Hybrid Mode) ──
        paths = []

        # 1. Add bundled site-packages (libs we ship: polars, duckdb, etc.)
        if FlowExecutor._is_bundled_app():
            bundled_sp = FlowExecutor._find_bundled_site_packages()
            if bundled_sp:
                paths.append(bundled_sp)
                logger.debug(f"Added bundled site-packages to PYTHONPATH: {bundled_sp}")

            # 2. Add system site-packages (libs user has: psycopg2, etc.)
            # only if we found a bundled runtime (if we are using system python,
            # it already sees its own site-packages)
            if FlowExecutor._find_bundled_python():
                system_sp = FlowExecutor._find_system_site_packages()
                if system_sp:
                    paths.append(system_sp)
                    logger.debug(
                        f"Added system site-packages to PYTHONPATH (Hybrid Mode): {system_sp}"
                    )

        # Add project root so user scripts can do:
        #   from src import dataengine   OR   from dataryx import dataengine
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        paths.append(project_root)

        if paths:
            existing = env.get("PYTHONPATH", "")
            if existing:
                env["PYTHONPATH"] = os.pathsep.join(paths) + os.pathsep + existing
            else:
                env["PYTHONPATH"] = os.pathsep.join(paths)

        return env

    @staticmethod
    def start_script(
        script_path: str,
        params: Dict[str, Any],
        credentials: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> tuple[Optional[subprocess.Popen], str]:
        """
        Starts a python script as a separate process.
        """
        from datetime import datetime

        start_time_iso = datetime.now().isoformat()

        if not os.path.exists(script_path):
            logger.error(f"Script not found: {script_path}")
            return None, start_time_iso

        try:
            env = FlowExecutor._get_clean_env(params, credentials)
            cmd = FlowExecutor._get_subprocess_args(script_path)
            flags = FlowExecutor._get_creation_flags()

            logger.info(f"Starting script in background: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                stdin=subprocess.DEVNULL,  # Ensure it doesn't wait for input
                text=True,
                encoding="utf-8",
                creationflags=flags,
            )
            return process, start_time_iso

        except Exception as e:
            logger.error(f"Error starting script {script_path}: {e}")
            return None, start_time_iso

    @staticmethod
    def run_script(
        script_path: str,
        params: Dict[str, Any],
        credentials: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> tuple[bool, str, float, str]:
        """
        Executes a python script as a separate process (blocking version).
        """
        import time
        from datetime import datetime

        start_time_iso = datetime.now().isoformat()
        start_time = time.time()

        if not os.path.exists(script_path):
            return False, f"Script not found: {script_path}", 0.0, start_time_iso

        try:
            env = FlowExecutor._get_clean_env(params, credentials)
            cmd = FlowExecutor._get_subprocess_args(script_path)
            flags = FlowExecutor._get_creation_flags()

            logger.info(f"Running script: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
            )

            duration = round(time.time() - start_time, 2)
            logs = result.stdout
            if result.stderr:
                logs += f"\nSTDERR:\n{result.stderr}"
            return True, logs, duration, start_time_iso

        except subprocess.CalledProcessError as e:
            duration = round(time.time() - start_time, 2)
            logs = f"Process failed with code {e.returncode}\n"
            if e.stdout:
                logs += f"STDOUT:\n{e.stdout}\n"
            if e.stderr:
                logs += f"STDERR:\n{e.stderr}"
            return False, logs, duration, start_time_iso

        except Exception as e:
            duration = round(time.time() - start_time, 2)
            return False, f"Execution error: {e}", duration, start_time_iso
