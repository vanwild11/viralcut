"""Сборка ViralCut для macOS (Apple Silicon) и Windows 10/11 (x64)."""
import re as _re
from pathlib import Path as _Path


def _read_version() -> str:
    """Версия берётся из viralcut/_version.py — единый источник истины.

    PyInstaller исполняет spec без `__file__`, поэтому берём SPECPATH, который
    он выставляет сам (каталог спецификации = корень проекта).
    """
    base = _Path(globals().get("SPECPATH") or ".")
    source = base / "viralcut" / "_version.py"
    try:
        match = _re.search(r'__version__\s*=\s*"([^"]+)"', source.read_text(encoding="utf-8"))
    except OSError:
        return "0.0.0"
    return match.group(1) if match else "0.0.0"


_APP_VERSION = _read_version()

import glob
import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

datas = [("web", "web"), ("assets", "assets")]

# Node + PO-провайдер для HD с YouTube. На Windows архив собирается отдельно,
# без него приложение работает, но YouTube может ограничиться 360p.
vendor = Path("desktop/vendor.tar.gz")
if vendor.is_file():
    datas.append((str(vendor), "bundle"))

# Модель Whisper Small: из кэша проекта или из подготовленной папки build/whisper-small.
snapshots = glob.glob("data/models/models--Systran--faster-whisper-small/snapshots/*")
built_model = Path("build/whisper-small")
if snapshots and not (built_model / "model.bin").is_file():
    src = Path(snapshots[0])
    shutil.rmtree(built_model, ignore_errors=True)
    built_model.mkdir(parents=True, exist_ok=True)
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
        file = src / name
        if file.exists():
            shutil.copy2(file.resolve(), built_model / name)
if (built_model / "model.bin").is_file():
    datas.append((str(built_model), "models/whisper-small"))

binaries = []
if IS_WIN:
    # Python.Runtime.dll (netfx) ищет python3XX.dll рядом с собой — кладём копию.
    _py_dll = Path(sys.base_prefix) / f"python{sys.version_info[0]}{sys.version_info[1]}.dll"
    if _py_dll.is_file():
        binaries.append((str(_py_dll), "pythonnet/runtime"))

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "anyio._backends._asyncio",
    "viralcut.diagnostics",  # разбор app.log импортируется из эндпоинта лениво
] + collect_submodules("yt_dlp_plugins") + collect_submodules("fontTools")

if IS_MAC:
    hiddenimports += ["objc", "Foundation", "AppKit", "WebKit", "Quartz",
                      "UniformTypeIdentifiers", "Security"]
if IS_WIN:
    # pywebview на Windows использует WebView2/EdgeChromium через pythonnet;
    # collect_all кладёт WebView2Loader.dll, Microsoft.Web.WebView2.* и Python.Runtime.dll.
    for pkg in ("webview", "pythonnet", "clr_loader"):
        pkg_datas, pkg_binaries, _pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
    hiddenimports += [
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "clr",
        "clr_loader",
        "pythonnet",
    ]

for package in ("ctranslate2", "faster_whisper", "tokenizers", "onnxruntime", "av",
                "huggingface_hub", "imageio_ffmpeg", "cv2", "googleapiclient", "keyring"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["desktop/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["desktop/pyi_rth_pythonnet.py"] if IS_WIN else [],
    excludes=["tkinter", "matplotlib", "PyQt5", "PyQt6", "PySide6", "IPython", "pytest",
              "notebook", "jupyter"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ViralCut",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    disable_windowed_traceback=False,
    icon="assets/ViralCut.ico" if IS_WIN else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ViralCut",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="ViralCut.app",
        icon="assets/ViralCut.icns",
        bundle_identifier="com.viralcut.app",
        version=_APP_VERSION,
        info_plist={
            "CFBundleDisplayName": "ViralCut",
            "CFBundleShortVersionString": _APP_VERSION,
            "CFBundleVersion": _APP_VERSION,
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSApplicationCategoryType": "public.app-category.video",
            "NSHumanReadableCopyright": "ViralCut",
        },
    )
