"""System Hardware & Tool Diagnostic Tool.

Verifies:
  - System RAM & CPU cores (with 16GB / Iris iGPU recommendations)
  - ffmpeg availability & version
  - yt-dlp availability & version
  - WeasyPrint & GTK/Pango runtime (plus headless Chrome/Edge PDF fallback)
  - Ollama local daemon status & required models (qwen2.5:7b, qwen2.5:3b)
  - Settings & environment configuration

Usage:
    python -m backend.check_system
"""

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import psutil

# Ensure project root is in sys.path regardless of working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings


def check_ram():
    mem = psutil.virtual_memory()
    total_gb = mem.total / (1024 ** 3)
    available_gb = mem.available / (1024 ** 3)
    percent_used = mem.percent

    print("\n[1/6] RAM Status")
    print(f"  Total RAM:     {total_gb:.2f} GB")
    print(f"  Available RAM: {available_gb:.2f} GB ({100 - percent_used:.1f}% free)")
    print(f"  Used RAM:      {mem.used / (1024 ** 3):.2f} GB ({percent_used}%)")

    if total_gb < 8:
        print("  [!] WARNING: Less than 8 GB total RAM. Local inference may encounter OOM errors.")
    elif total_gb <= 16:
        print("  [+] Optimal for 16 GB RAM setup:")
        print("      * Whisper: CPU int8 model 'small' (~1.5 GB RAM)")
        print("      * LLM: Gemini Cloud (0 GB RAM) or Ollama Fast Mode qwen2.5:3b (~2.5 GB RAM)")
        print("      * Sequential pipeline frees Whisper memory before invoking LLM.")
    else:
        print("  [+] Ample RAM available (>16 GB). Suitable for local 7B models.")

    return total_gb, available_gb


def check_cpu():
    physical_cores = psutil.cpu_count(logical=False) or 1
    logical_cores = psutil.cpu_count(logical=True) or 1

    print("\n[2/6] CPU Cores & Threads")
    print(f"  Physical Cores: {physical_cores}")
    print(f"  Logical Cores:  {logical_cores}")
    recommended_threads = max(1, min(4, logical_cores - 1))
    print(f"  Recommended WHISPER_THREADS: {recommended_threads}")
    return physical_cores, logical_cores, recommended_threads


def find_ffmpeg_path() -> tuple[bool, str, str]:
    """Find ffmpeg in PATH or common Windows / WinGet locations."""
    # 1. Check system PATH
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return _test_ffmpeg(which_ffmpeg)

    # 2. Check Windows WinGet location
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_pattern = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages", "**", "ffmpeg.exe")
        matches = glob.glob(winget_pattern, recursive=True)
        if matches:
            return _test_ffmpeg(matches[0])

    # 3. Common directory fallback
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe"),
    ]
    for p in common_paths:
        if os.path.exists(p):
            return _test_ffmpeg(p)

    return False, "", "ffmpeg not found"


def _test_ffmpeg(path: str) -> tuple[bool, str, str]:
    try:
        res = subprocess.run([path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if res.returncode == 0:
            first_line = res.stdout.splitlines()[0] if res.stdout else "version unknown"
            return True, path, first_line
    except Exception as e:
        return False, path, str(e)
    return False, path, "Execution failed"


def check_ffmpeg():
    print("\n[3/6] FFmpeg Audio Extraction Tool")
    found, path, version_info = find_ffmpeg_path()
    if found:
        print(f"  [+] FFmpeg is installed and working.")
        print(f"      Path:    {path}")
        print(f"      Version: {version_info}")
        return True
    else:
        print("  [-] FFmpeg NOT found in PATH or standard directories.")
        print("      FFmpeg is required to extract 16kHz mono WAV audio from videos.")
        print("\n      Installation Instructions:")
        print("      * Windows: Run `winget install Gyan.FFmpeg` or download from https://ffmpeg.org/download.html")
        print("      * Ubuntu / Debian: Run `sudo apt update && sudo apt install ffmpeg`")
        print("      * macOS: Run `brew install ffmpeg`")
        return False


def check_ytdlp():
    print("\n[4/6] yt-dlp Video / Audio Downloader")
    ytdlp_exe = shutil.which("yt-dlp")
    import_ok = False
    try:
        import yt_dlp
        import_ok = True
    except ImportError:
        pass

    if ytdlp_exe or import_ok:
        version_str = "installed"
        if ytdlp_exe:
            try:
                res = subprocess.run([ytdlp_exe, "--version"], stdout=subprocess.PIPE, text=True, timeout=5)
                version_str = res.stdout.strip()
            except Exception:
                pass
        print(f"  [+] yt-dlp is available.")
        if ytdlp_exe:
            print(f"      Executable: {ytdlp_exe} (version {version_str})")
        if import_ok:
            print("      Python module: yt_dlp [OK]")
        return True
    else:
        print("  [-] yt-dlp is NOT installed.")
        print("      Installation Instructions:")
        print("      * Run: `pip install yt-dlp`")
        print("      * Or Windows: `winget install yt-dlp`")
        return False


def check_pdf_engine():
    print("\n[5/6] PDF Generation Engine (WeasyPrint & GTK/Pango Runtime)")
    project_root = Path(__file__).resolve().parent.parent
    standalone_wp = project_root / "bin" / "weasyprint" / "onedir" / "weasyprint" / "weasyprint.exe"

    standalone_ok = False
    if standalone_wp.exists():
        try:
            res = subprocess.run([str(standalone_wp), "--version"], stdout=subprocess.PIPE, text=True, timeout=5)
            if res.returncode == 0:
                print(f"  [+] Standalone WeasyPrint binary detected and working.")
                print(f"      Path:    {standalone_wp}")
                print(f"      Version: {res.stdout.strip()}")
                standalone_ok = True
        except Exception as e:
            print(f"  [!] Standalone WeasyPrint exists but failed to execute: {e}")

    # Check python weasyprint module
    python_wp_ok = False
    try:
        # Check WEASYPRINT_DLL_DIRECTORIES or default MSYS2 path if on Windows
        if sys.platform == "win32":
            msys_bin = os.environ.get("WEASYPRINT_DLL_DIRECTORIES", r"C:\msys64\mingw64\bin")
            if os.path.exists(msys_bin) and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(msys_bin)

        import weasyprint
        # Try a quick rendering check to verify GTK libraries
        pdf_bytes = weasyprint.HTML(string="<p>test</p>").write_pdf()
        if pdf_bytes and len(pdf_bytes) > 100:
            print(f"  [+] Python weasyprint module is fully functional (GTK3 / Pango loaded).")
            python_wp_ok = True
    except Exception as e:
        err = str(e)
        if "libgobject" in err or "cannot load library" in err:
            print(f"  [i] Python weasyprint import: Missing GTK/Pango C libraries ({err.split(':')[0]}).")
            print("      Exact Windows Fix Steps:")
            print("      1. Install MSYS2 from https://www.msys2.org/")
            print("      2. In MSYS2 terminal run: pacman -S mingw-w64-x86_64-pango")
            print(r"      3. Add C:\msys64\mingw64\bin to PATH or set WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin")
            if standalone_ok:
                print("      -> Safe to proceed: The app automatically routes through the standalone WeasyPrint binary.")
        else:
            print(f"  [!] Python weasyprint error: {e}")

    # Detect Chrome / Edge fallback
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    browser_fallback = None
    for p in chrome_paths + edge_paths:
        if os.path.exists(p):
            browser_fallback = p
            break

    if browser_fallback:
        print(f"  [+] Headless Browser Fallback available: {browser_fallback}")
        print("      Command: <browser> --headless --print-to-pdf=output.pdf input.html")

    if not standalone_ok and not python_wp_ok:
        print("  [-] No functional WeasyPrint engine found.")
        print("\n      Exact Windows Fix Steps:")
        print("      1. Run `winget install Gyan.FFmpeg` (if ffmpeg missing)")
        print("      2. Install MSYS2 and run: `pacman -S mingw-w64-x86_64-pango`")
        print(r"      3. Add C:\msys64\mingw64\bin to PATH or set WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin")
        print("      4. Or download the standalone WeasyPrint release from:")
        print("         https://github.com/Kozea/WeasyPrint/releases (extract to bin/weasyprint/)")
        if browser_fallback:
            print(f"      5. Or HTML-to-PDF Fallback: Headless Chrome at: {browser_fallback}")
        return False

    return True


def check_ollama():
    settings = get_settings()
    base_url = settings.OLLAMA_BASE_URL
    print(f"\n[6/6] Ollama Local Daemon ({base_url})")

    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{base_url.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                print(f"  [+] Ollama is running and responding.")
                print(f"      Installed models ({len(models)}): {', '.join(models) if models else 'None'}")

                has_7b = any(settings.OLLAMA_MODEL in m for m in models)
                has_3b = any(settings.OLLAMA_FAST_MODEL in m for m in models)

                print(f"      - Standard Model ({settings.OLLAMA_MODEL}): {'[READY]' if has_7b else '[NOT PULLED]'}")
                print(f"      - Fast Mode Model ({settings.OLLAMA_FAST_MODEL}): {'[READY]' if has_3b else '[NOT PULLED]'}")

                if not has_7b:
                    print(f"        -> To pull standard model: `ollama pull {settings.OLLAMA_MODEL}`")
                if not has_3b:
                    print(f"        -> To pull fast mode model: `ollama pull {settings.OLLAMA_FAST_MODEL}`")

                return True
            else:
                print(f"  [!] Ollama responded with HTTP {resp.status_code}")
                return False
    except Exception:
        print(f"  [-] Ollama daemon is NOT running at {base_url}.")
        print("      Local AI inference will be unavailable until Ollama is started.")
        print("\n      Installation & Start Instructions:")
        print("      * Windows: `winget install Ollama.Ollama` or download from https://ollama.com/download")
        print("      * Linux / macOS: `curl -fsSL https://ollama.com/install.sh | sh`")
        print("      * Start daemon: `ollama serve`")
        print(f"      * Pull model:   `ollama pull {settings.OLLAMA_FAST_MODEL}` (fast mode, recommended for 16GB RAM)")
        return False


def main():
    print("=" * 65)
    print("   LectureNotes AI -- Comprehensive System & Tool Diagnostic")
    print("=" * 65)

    check_ram()
    check_cpu()
    check_ffmpeg()
    check_ytdlp()
    check_pdf_engine()
    check_ollama()

    settings = get_settings()
    print("\n" + "=" * 65)
    print("Current Configuration (.env):")
    print(f"  LLM_PROVIDER:      {settings.LLM_PROVIDER}")
    print(f"  GEMINI_MODEL:      {settings.GEMINI_MODEL or '(Not set - run python -m backend.llm.check)'}")
    print(f"  OLLAMA_MODEL:      {settings.OLLAMA_MODEL}")
    print(f"  OLLAMA_FAST_MODEL: {settings.OLLAMA_FAST_MODEL}")
    print(f"  WHISPER_MODEL:     {settings.WHISPER_MODEL} ({settings.WHISPER_DEVICE}, {settings.WHISPER_COMPUTE_TYPE})")
    print(f"  DEMO_MODE:         {settings.DEMO_MODE}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
