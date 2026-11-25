"""Скачивает Windows-колёса всех зависимостей ViralCut, запускаясь с macOS/Linux.

Зачем свой резолвер: `pip download --platform win_amd64` выбирает колёса под
Windows, но **маркеры окружения** (sys_platform и т.п.) вычисляет в текущей ОС.
Из-за этого pywebview тянет pyobjc (mac), а pythonnet наоборот пропускается.
Здесь зависимости обходятся по METADATA: маркеры считаются в окружении win32.

Использование:
    python tools/resolve_windows_wheels.py --dest build/windows-wheels

Результат — папка с .whl (и пара sdist для пакетов вроде proxy-tools), которую
потом использует tools/build_windows_embedded.sh.
"""
from __future__ import annotations

import argparse
import email.parser
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

TOP = [
    "fastapi", "uvicorn", "yt-dlp", "imageio-ffmpeg", "faster-whisper",
    "av==15.1.0", "Pillow", "fonttools", "numpy", "opencv-python-headless",
    "python-multipart", "bgutil-ytdlp-pot-provider", "pywebview==6.2.1",
    "pythonnet==3.0.5", "clr-loader==0.2.7.post0", "proxy-tools==0.1.0",
]

# proxy-tools распространяется только sdist. Фиксируем хеш и собираем wheel
# здесь же, иначе в Windows-сборку попадёт исходник без метаданных wheel.
PROXY_TOOLS_SHA256 = "ccb3751f529c047e2d8a58440d86b205303cf0fe8146f784d1cbcd94f0a28010"

WINDOWS_ENV = {
    "sys_platform": "win32",
    "platform_system": "Windows",
    "os_name": "nt",
    "platform_machine": "AMD64",
    "python_version": "3.12",
    "python_full_version": "3.12.10",
    "implementation_name": "cpython",
    "implementation_version": "3.12.10",
    "platform_python_implementation": "CPython",
    "extra": "",
}

# uvicorn[standard] на Windows не тянет uvloop; список extras раскрываем сами,
# а на macOS маркер «стандартных» зависимостей может отличаться.
UVICORN_STANDARD = ["httptools", "websockets", "watchfiles", "python-dotenv", "PyYAML",
                    "click", "h11"]


def _pip_download(spec: str, dest: Path, *, source: bool = False) -> Path | None:
    cmd = [sys.executable, "-m", "pip", "download", "--no-deps", "--quiet",
           "--dest", str(dest)]
    if source:
        cmd += ["--no-binary=:all:"]
    else:
        cmd += ["--platform", "win_amd64", "--python-version", "3.12",
                "--implementation", "cp", "--abi", "cp312", "--only-binary=:all:"]
    cmd.append(spec)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    files = sorted(Path(dest).glob("*.whl")) or sorted(Path(dest).glob("*.tar.gz"))
    return files[0] if files else None


def _wheel_metadata(path: Path) -> tuple[str, Version, list[str], set[str]]:
    payload: bytes
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            payload = archive.read(name)
    elif path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            name = next(n for n in archive.namelist() if n.endswith("PKG-INFO"))
            payload = archive.read(name)
    else:
        with tarfile.open(path, "r:gz") as archive:
            member = next(m for m in archive.getmembers() if m.name.endswith("PKG-INFO"))
            payload = archive.extractfile(member).read()  # type: ignore[union-attr]
    message = email.parser.Parser().parsestr(payload.decode("utf-8", "replace"))
    return (canonicalize_name(message["Name"]), Version(message["Version"]),
            message.get_all("Requires-Dist") or [], set(message.get_all("Provides-Extra") or []))


def _requirements(lines: list[str], extra: str) -> list[Requirement]:
    out: list[Requirement] = []
    for line in lines:
        req = Requirement(line)
        if req.marker is not None:
            try:
                if not req.marker.evaluate(dict(WINDOWS_ENV, extra=extra)):
                    continue
            except Exception:  # noqa: BLE001
                continue
        out.append(req)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Windows-колёса для переносимой сборки")
    parser.add_argument("--dest", default="build/windows-wheels", type=Path)
    parser.add_argument("--python", default="3.12")
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    sdists = args.dest / "sdists"
    sdists.mkdir(exist_ok=True)

    # extras раскрываем вручную: pip с --platform вычисляет маркеры в macOS
    queue = [Requirement(spec) for spec in [*TOP, *UVICORN_STANDARD]]
    resolved: dict[str, Version] = {}
    seen: set[tuple[str, str]] = set()

    while queue:
        req, extra = queue.pop(0), ""
        if isinstance(req, tuple):
            req, extra = req
        key = (canonicalize_name(req.name), extra)
        if key in seen:
            continue
        seen.add(key)
        name = canonicalize_name(req.name)
        if name in resolved:
            continue
        with tempfile.TemporaryDirectory(prefix="vc-wheels-") as tmp:
            spec = f"{req.name}{req.specifier}"
            path = _pip_download(spec, Path(tmp))
            if path is None:
                path = _pip_download(spec, Path(tmp), source=True)
            if path is None:
                print(f"!! не скачалось: {spec}")
                continue
            if name == "proxy-tools" and path.name.endswith(".tar.gz"):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != PROXY_TOOLS_SHA256:
                    raise SystemExit(f"proxy-tools: не совпал SHA-256: {digest}")
                build = subprocess.run(
                    [sys.executable, "-m", "pip", "wheel", "--no-deps",
                     "--wheel-dir", tmp, str(path)],
                    capture_output=True, text=True,
                )
                if build.returncode != 0:
                    raise SystemExit(f"proxy-tools: не собрался wheel:\n{build.stderr}")
                wheels = sorted(Path(tmp).glob("proxy_tools-*.whl"))
                if len(wheels) != 1:
                    raise SystemExit(f"proxy-tools: ожидался один wheel, найдено {len(wheels)}")
                path = wheels[0]
            target = args.dest / path.name
            if not target.exists():
                shutil.copy2(path, target)
        real_name, version, requires, extras = _wheel_metadata(target)
        resolved[real_name] = version
        print(f"OK {real_name}=={version}")
        for dep in _requirements(requires, extra):
            queue.append((dep, ""))
            for ex in sorted(dep.extras):
                if ex in extras:
                    queue.append((dep, ex))

    print(f"\nПакетов: {len(resolved)}")
    for name in sorted(resolved):
        print(f"  {name}=={resolved[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
