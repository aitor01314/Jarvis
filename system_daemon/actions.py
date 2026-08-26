"""Acciones de control del sistema operativo (Windows primero).

Este módulo es la única pieza de JARVIS que toca el SO. El core
nunca lo importa directamente: habla con el daemon por HTTP.
"""

from __future__ import annotations

import os
import subprocess

import psutil

# Alias en español -> ejecutable de Windows.
APP_ALIASES: dict[str, str] = {
    "bloc de notas": "notepad",
    "notepad": "notepad",
    "calculadora": "calc",
    "explorador": "explorer",
    "explorador de archivos": "explorer",
    "paint": "mspaint",
    "chrome": "chrome",
    "navegador": "chrome",
    "edge": "msedge",
    "terminal": "wt",
    "cmd": "cmd",
    "powershell": "powershell",
    "visual studio code": "code",
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "spotify": "spotify",
    "word": "winword",
    "excel": "excel",
    "administrador de tareas": "taskmgr",
}


# Algunas apps lanzan un proceso con nombre distinto al ejecutable.
PROCESS_VARIANTS: dict[str, set[str]] = {
    "calc": {"calc", "calculatorapp", "calculator", "win32calc"},
    "wt": {"wt", "windowsterminal"},
    "code": {"code"},
}


def resolve_app(name: str) -> str:
    return APP_ALIASES.get(name.strip().lower(), name.strip())


def open_app(name: str) -> dict:
    executable = resolve_app(name)
    subprocess.Popen(
        ["cmd", "/c", "start", "", executable],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"ok": True, "accion": "abrir", "aplicacion": executable}


def close_app(name: str) -> dict:
    executable = resolve_app(name)
    target = executable.lower().removesuffix(".exe")
    targets = PROCESS_VARIANTS.get(target, {target})
    closed = 0
    for proc in psutil.process_iter(["name"]):
        proc_name = (proc.info["name"] or "").lower().removesuffix(".exe")
        if proc_name in targets:
            try:
                proc.terminate()
                closed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    return {"ok": closed > 0, "accion": "cerrar", "aplicacion": executable, "procesos": closed}


def metrics() -> dict:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    data: dict = {
        "cpu_porcentaje": psutil.cpu_percent(interval=0.3),
        "cpu_nucleos": psutil.cpu_count(),
        "ram_porcentaje": memory.percent,
        "ram_usada_gb": round(memory.used / 1024**3, 2),
        "ram_total_gb": round(memory.total / 1024**3, 2),
        "disco_porcentaje": disk.percent,
        "procesos": len(psutil.pids()),
    }
    data["gpu"] = _gpu_metrics()
    return data


def _gpu_metrics() -> list[dict]:
    try:
        import pynvml

        pynvml.nvmlInit()
        gpus = []
        for i in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpus.append(
                {
                    "nombre": pynvml.nvmlDeviceGetName(handle),
                    "uso_porcentaje": util.gpu,
                    "vram_usada_gb": round(mem.used / 1024**3, 2),
                    "vram_total_gb": round(mem.total / 1024**3, 2),
                }
            )
        pynvml.nvmlShutdown()
        return gpus
    except Exception:  # noqa: BLE001 - sin GPU NVIDIA o sin driver
        return []


def list_processes(limit: int = 15) -> list[dict]:
    procs = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            mem = proc.info["memory_info"]
            procs.append(
                {
                    "pid": proc.info["pid"],
                    "nombre": proc.info["name"],
                    "ram_mb": round((mem.rss if mem else 0) / 1024**2, 1),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda p: p["ram_mb"], reverse=True)
    return procs[:limit]


def clipboard_get() -> dict:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {"contenido": result.stdout.rstrip("\r\n")}


def clipboard_set(text: str) -> dict:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $env:JARVIS_CLIP"],
        env={**os.environ, "JARVIS_CLIP": text},
        check=False,
    )
    return {"ok": True}
