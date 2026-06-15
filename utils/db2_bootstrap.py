import sys
import os
import pathlib

def register():
    """
    Registers the IBM DB2 clidriver DLL directories for the current process.
    Required for Python 3.8+ on Windows to load ibm_db.
    """
    if sys.platform != "win32":
        return

    base = pathlib.Path(sys.executable).parent
    # Standard locations for site-packages and bundled drivers
    candidates = [
        base.parent / "Lib" / "site-packages" / "clidriver" / "bin",  # Local .venv
        base / "site-packages" / "clidriver" / "bin",                 # Bundled site-packages
        base / "clidriver" / "bin",                                   # Bundled root
        base.parent / "site-packages" / "clidriver" / "bin",          # Parallel to python_runtime
        base.parent.parent / "site-packages" / "clidriver" / "bin",   # Deep parallel
        base / "_internal" / "clidriver" / "bin",                     # PyInstaller-style internal
    ]
    
    # Try absolute discovery relative to this file as a fallback
    try:
        cur_file = pathlib.Path(__file__).absolute()
        # src/utils/db2_bootstrap.py -> src/
        src_dir = cur_file.parent.parent
        candidates.append(src_dir.parent / "site-packages" / "clidriver" / "bin")
    except Exception:
        pass

    found_bin = None
    for p in candidates:
        if p.exists():
            found_bin = p
            
            # 1. Add bin to DLL search path
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(p))
                except Exception:
                    pass
            
            # 2. Add SSL/ICC dependencies if they exist
            icc_path = p / "icc64" if (p / "icc64").exists() else p / "icc"
            if icc_path.exists() and hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(icc_path))
                except Exception:
                    pass

            # 3. Add bundled MSVC runtimes (e.g. amd64.VC12.CRT for msvcr120.dll)
            crt_path = p / "amd64.VC12.CRT" if (p / "amd64.VC12.CRT").exists() else p / "x86.VC12.CRT"
            if crt_path.exists() and hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(crt_path))
                    os.environ["PATH"] = str(crt_path) + os.pathsep + os.environ.get("PATH", "")
                except Exception:
                    pass

            # 4. Setup required Environment Variables
            os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")
            os.environ["IBM_DB_HOME"] = str(p.parent)
            
            # Dummy instance for driver initialization
            if "DB2INSTANCE" not in os.environ:
                os.environ["DB2INSTANCE"] = "DB2"
            
            # Ensure the driver has a writable location for its internal logs/cfg
            app_data = os.environ.get("APPDATA") or os.environ.get("USERPROFILE")
            if app_data:
                db2_data = pathlib.Path(app_data) / ".db2_data"
                try:
                    db2_data.mkdir(exist_ok=True, parents=True)
                    os.environ["DB2_COMMON_APP_DATA_TOP"] = str(db2_data)
                except Exception:
                    pass
            
            # --- Subprocess Safety (Auto-Repair sitecustomize.py) ---
            # To fix subprocesses (flows) which ignore PYTHONPATH due to .pth files,
            # we ensure sitecustomize.py exists in the site-packages directory.
            try:
                sp_dir = p.parent.parent # Usually clidriver is in site-packages
                sc_path = sp_dir / "sitecustomize.py"
                
                sc_content = (
                    "import sys, os, pathlib\n"
                    "def _db2_bootstrap():\n"
                    "    if sys.platform != 'win32': return\n"
                    "    base = pathlib.Path(sys.executable).parent\n"
                    "    candidates = [\n"
                    f"        pathlib.Path(r'{p}'),\n"  # Exact current path
                    "        base.parent / 'Lib' / 'site-packages' / 'clidriver' / 'bin',\n"
                    "        base / 'site-packages' / 'clidriver' / 'bin',\n"
                    "        base / 'clidriver' / 'bin',\n"
                    "        base.parent.parent / 'site-packages' / 'clidriver' / 'bin',\n"
                    "    ]\n"
                    "    for p in candidates:\n"
                    "        if p.exists():\n"
                    "            if hasattr(os, 'add_dll_directory'):\n"
                    "                try: os.add_dll_directory(str(p))\n"
                    "                except: pass\n"
                    "            icc = p / 'icc64' if (p / 'icc64').exists() else p / 'icc'\n"
                    "            if icc.exists() and hasattr(os, 'add_dll_directory'):\n"
                    "                try: os.add_dll_directory(str(icc))\n"
                    "                except: pass\n"
                    "            crt = p / 'amd64.VC12.CRT' if (p / 'amd64.VC12.CRT').exists() else p / 'x86.VC12.CRT'\n"
                    "            if crt.exists() and hasattr(os, 'add_dll_directory'):\n"
                    "                try: \n"
                    "                    os.add_dll_directory(str(crt))\n"
                    "                    os.environ['PATH'] = str(crt) + os.pathsep + os.environ.get('PATH', '')\n"
                    "                except: pass\n"
                    "            os.environ['PATH'] = str(p) + os.pathsep + os.environ.get('PATH', '')\n"
                    "            os.environ['IBM_DB_HOME'] = str(p.parent)\n"
                    "            if 'DB2INSTANCE' not in os.environ: os.environ['DB2INSTANCE'] = 'DB2'\n"
                    "            break\n"
                    "try: _db2_bootstrap()\n"
                    "except: pass\n"
                )
                
                # Only write if missing or different to avoid overhead
                if not sc_path.exists() or sc_path.read_text(encoding="utf-8") != sc_content:
                    sc_path.write_text(sc_content, encoding="utf-8")
            except Exception:
                pass
                
            break

