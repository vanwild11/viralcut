#!/usr/bin/env bash
# Переносимая Windows-сборка «всё внутри»: встроенный Python, зависимости,
# модель Whisper и Node/PO-провайдер. Пользователь распаковывает ZIP и запускает
# ViralCut.exe. Запускатель использует Python и зависимости из архива.
# Для сборки запускателя нужен Python с pip и distlib.
#
# Подготовка колёс (один раз):
#   python tools/resolve_windows_wheels.py --dest build/windows-wheels
# WINDOWS_VENDOR указывает на папку Windows x64 с node.exe, pot/ и ejs/.
# Сборка:
#   ./tools/build_windows_embedded.sh
set -euo pipefail
cd "$(dirname "$0")/.."

BUILD_PYTHON="${BUILD_PYTHON:-python3}"
VERSION="$("$BUILD_PYTHON" tools/version.py)"
PY_EMBED_VER="${PY_EMBED_VER:-3.12.10}"
WHEELS="${WHEELS:-build/windows-wheels}"
MODEL="${MODEL:-build/whisper-small}"
WINDOWS_VENDOR="${WINDOWS_VENDOR:-build/windows-vendor-x64}"
STAGE="build/windows-embedded"
OUTDIR="dist"
NAME="ViralCut-${VERSION}-windows-x64-portable"
OUT="$OUTDIR/$NAME.zip"

[ -d "$WHEELS" ] || { echo "Нет колёс: $WHEELS. Запустите tools/resolve_windows_wheels.py"; exit 1; }
[ -f "$MODEL/model.bin" ] || { echo "Нет модели: $MODEL/model.bin"; exit 1; }

python3 - "$WINDOWS_VENDOR" <<'PY'
import struct
import sys
from pathlib import Path

vendor = Path(sys.argv[1])
for marker in ("pot/build/main.js", "ejs/challenge-solver/lib.json"):
    if not (vendor / marker).is_file():
        raise SystemExit(f"В Windows-комплекте провайдера нет {marker}: {vendor}")

for relative in ("node.exe", "pot/node_modules/canvas/build/Release/canvas.node"):
    path = vendor / relative
    if not path.is_file():
        raise SystemExit(f"Не найден бинарник Windows x64: {path}")
    with path.open("rb") as binary:
        header = binary.read(64)
        if len(header) == 64 and header.startswith(b"MZ"):
            binary.seek(struct.unpack_from("<I", header, 60)[0])
            if binary.read(6) == b"PE\x00\x00\x64\x86":
                continue
    raise SystemExit(f"Ожидался PE-бинарник Windows x64: {path}")

if any(path.is_symlink() for path in vendor.rglob("*")):
    raise SystemExit(f"В Windows-комплекте провайдера не должно быть симлинков: {vendor}")
PY

PYCACHE="build/python-embed-$PY_EMBED_VER.zip"
if [ ! -f "$PYCACHE" ]; then
  mkdir -p build
  echo "Качаю Python $PY_EMBED_VER (embeddable)..."
  curl -fL --retry 3 -o "$PYCACHE" \
    "https://www.python.org/ftp/python/$PY_EMBED_VER/python-$PY_EMBED_VER-embed-amd64.zip"
fi

rm -rf "$STAGE"
APPDIR="$STAGE/ViralCut"
mkdir -p "$APPDIR"/{python,site-packages,desktop,tools,models}

echo "Распаковываю Python..."
unzip -q "$PYCACHE" -d "$APPDIR/python"

echo "Распаковываю колёса..."
for wheel in "$WHEELS"/*.whl; do
  unzip -q -o "$wheel" -d "$APPDIR/site-packages"
done
rm -rf "$APPDIR"/site-packages/*.data

echo "sdist-пакеты (proxy-tools)..."
for sdist in "$WHEELS"/sdists/*.tar.gz; do
  [ -f "$sdist" ] || continue
  tmp="$(mktemp -d)"
  tar xzf "$sdist" -C "$tmp"
  for pkg in "$tmp"/*/; do
    base="$(basename "$pkg")"
    [ "$base" = "PKG-INFO" ] && continue
    if [ -f "$pkg/__init__.py" ] && [ ! -e "$APPDIR/site-packages/$base" ]; then
      cp -R "$pkg" "$APPDIR/site-packages/$base"
    fi
  done
  rm -rf "$tmp"
done

echo "Копирую приложение..."
cp -R viralcut "$APPDIR/viralcut"
cp -R web "$APPDIR/web"
cp -R assets "$APPDIR/assets"
cp desktop/main.py "$APPDIR/desktop/main.py"
cp -R "$WINDOWS_VENDOR" "$APPDIR/desktop/vendor"
cp tools/analyze_app_log.py "$APPDIR/tools/analyze_app_log.py"
cp LICENSE "$APPDIR/LICENSE"
cp -R "$MODEL" "$APPDIR/models/whisper-small"
find "$APPDIR" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$APPDIR" -name ".DS_Store" -delete 2>/dev/null || true

# Статическая проверка: окно на Windows требует ровно эти версии и файлы.
# Импорт WinForms проверяется на Windows через Verify.bat внутри архива.
python3 - "$APPDIR" <<'PY'
import sys
from pathlib import Path

site = Path(sys.argv[1]) / "site-packages"
required = [
    site / "uvicorn" / "__init__.py",
    site / "proxy_tools" / "__init__.py",
    site / "webview" / "platforms" / "winforms.py",
    site / "webview" / "lib" / "Microsoft.Web.WebView2.Core.dll",
    site / "webview" / "lib" / "Microsoft.Web.WebView2.WinForms.dll",
    site / "webview" / "lib" / "WebBrowserInterop.x64.dll",
    site / "pythonnet" / "runtime" / "Python.Runtime.dll",
]
missing = [str(path.relative_to(site)) for path in required if not path.is_file()]
if missing:
    raise SystemExit("В переносимой сборке нет обязательных файлов: " + ", ".join(missing))

for package, expected in (("pythonnet", "3.0.5"), ("clr_loader", "0.2.7.post0")):
    metadata = list(site.glob(f"{package}-*.dist-info/METADATA"))
    if len(metadata) != 1:
        raise SystemExit(f"Ожидался ровно один {package}-*.dist-info, найдено {len(metadata)}")
    version = next(
        (line.split(":", 1)[1].strip() for line in metadata[0].read_text("utf-8", "replace").splitlines()
         if line.lower().startswith("version:")),
        "",
    )
    if version != expected:
        raise SystemExit(f"{package}: ожидалась версия {expected}, в сборке {version}")
PY

cat > "$APPDIR/python/python312._pth" <<'PTH'
python312.zip
.
..
..\site-packages
import site
PTH

python3 - "$APPDIR" "$VERSION" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
version = sys.argv[2]


def write(name: str, text: str) -> None:
    (root / name).write_bytes(text.replace("\n", "\r\n").encode("utf-8"))


write("ViralCut.bat", r'''@echo off
setlocal
cd /d "%~dp0"
set "PYTHONNET_PYDLL=%CD%\python\python312.dll"
set "PYTHONNET_RUNTIME=netfx"
set "VIRALCUT_WHISPER_DIR=%CD%\models\whisper-small"
set "VC_LOG=%APPDATA%\ViralCut\app.log"

rem Запуск без консоли. Если окно не появилось — показываем ошибку в консоли,
rem иначе пользователь видел «ничего не произошло» и не знал, что случилось.
start "" "%CD%\python\pythonw.exe" "%CD%\desktop\main.py"
timeout /t 4 /nobreak >nul
tasklist /FI "IMAGENAME eq pythonw.exe" 2>nul | find /I "pythonw.exe" >nul
if not errorlevel 1 exit /b 0

echo.
echo ViralCut не запустился. Ниже ошибка — её можно прислать разработчику.
echo.
"%CD%\python\python.exe" "%CD%\desktop\main.py"
echo.
if exist "%VC_LOG%" echo Лог: %VC_LOG%
pause
''')

write("ViralCut-console.bat", r'''@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONNET_PYDLL=%CD%\python\python312.dll"
set "PYTHONNET_RUNTIME=netfx"
set "VIRALCUT_WHISPER_DIR=%CD%\models\whisper-small"
echo Запуск ViralCut в консольном режиме (ошибки видны здесь)...
"%CD%\python\python.exe" "%CD%\desktop\main.py"
echo.
echo Приложение закрылось. Лог: %APPDATA%\ViralCut\app.log
pause
''')

write("Diagnostics.bat", r'''@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
"%CD%\python\python.exe" "%CD%\tools\analyze_app_log.py" %*
echo.
pause
''')

write("Verify.bat", r'''@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONNET_PYDLL=%CD%\python\python312.dll"
set "PYTHONNET_RUNTIME=netfx"
echo Проверка Python.NET, WinForms и WebView2...
"%CD%\python\python.exe" -c "import importlib.metadata as m, fastapi, uvicorn, clr, webview; from webview.platforms import winforms; print('OK', 'pythonnet', m.version('pythonnet'), 'clr-loader', m.version('clr-loader'), 'pywebview', m.version('pywebview'), 'renderer', winforms.renderer)"
if errorlevel 1 (
    echo.
    echo Проверка не пройдена. Пришлите вывод выше и %APPDATA%\ViralCut\app.log.
    pause
    exit /b 1
)
echo Проверка пройдена.
pause
''')

write("ViralCut.vbs", r'''Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root
sh.Run """" & root & "\ViralCut.bat""", 0, False
''')

write("README-WINDOWS-PORTABLE.txt", f'''ViralCut {version} — переносимая сборка для Windows 10/11 x64
==========================================================

Внутри Python, FFmpeg, модель распознавания речи и провайдер YouTube с Node.js для Windows x64.
Докачивать ничего не нужно — только распаковать и запустить.

Запуск
------
1. Распакуйте папку целиком (не запускайте из ZIP-архива).
2. Двойной клик по ViralCut.exe.

Если окно не открылось
----------------------
1. Запустите Verify.bat — он проверит Python.NET, WinForms и WebView2.
2. Запустите ViralCut-console.bat — там будет текст ошибки.
3. Пришлите %APPDATA%\\ViralCut\\app.log (или запустите Diagnostics.bat).
4. Windows 10 без WebView2 Runtime: поставьте «Microsoft Edge WebView2 Runtime»
   с сайта Microsoft (на Windows 11 он обычно уже есть).

Что проверить
-------------
1. Загрузка файла или ссылки, в параметрах — «Вырезать паузы».
2. «Пересобрать в 1080p» — окно не должно закрываться.
3. Виджет нагрузки: CPU/RAM/GPU (в подсказке — источник pdh/nvidia-smi/adl).
4. Настройки → «Разобрать журнал»: версия {version} и состояние системы.
5. Закрыть окно и снова открыть журнал: должен быть маркер stop.

Что прислать при проблеме
-------------------------
- app.log целиком (Diagnostics.bat) и на каком шаге упало.
- Версию Windows и модель видеокарты.

Ограничения
-----------
- Сборка собирается из win_amd64-колёс. Перед публикацией проверьте её на
  Windows 10/11: Verify.bat и запуск окна. Если что-то не запускается —
  пришлите app.log.
- Приложение не подписано: SmartScreen → «Подробнее» → «Выполнить всё равно».
- YouTube HD зависит от PO-token провайдера (Node внутри); при сбое — SD.
''')
PY

"$BUILD_PYTHON" tools/build_windows_launcher.py "$APPDIR"

mkdir -p "$OUTDIR"
rm -f "$OUT"
echo "Папую $OUT..."
(cd "$STAGE" && zip -rq -X -6 "../../$OUT" ViralCut)
SIZE="$(du -h "$OUT" | cut -f1 | tr -d ' ')"
SHA="$(shasum -a 256 "$OUT" | cut -d' ' -f1)"
printf '%s  %s\n' "$SHA" "$(basename "$OUT")" > "$OUTDIR/SHA256SUMS-windows-portable.txt"
echo "готово: $OUT ($SIZE)"
echo "sha256: $SHA"
