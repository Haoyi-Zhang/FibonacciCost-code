"""Validated runtime contract for the reproducibility scripts.

The retained resource fields use Linux ``getrusage`` semantics.  In particular,
``ru_maxrss`` is reported in KiB on Linux.  This module intentionally does not
invent a native-Windows fallback or silently relabel measurements from an
untested Unix variant.
"""
from __future__ import annotations

import platform
import sys
from types import ModuleType

MINIMUM_PYTHON = (3, 10)


def require_supported_environment(context: str) -> ModuleType:
    """Return :mod:`resource` after validating the documented Linux runtime.

    Unsupported platforms fail before scientific work or resource accounting is
    started.  Windows users should run the commands with Linux Python inside
    WSL2 rather than with native Windows Python.
    """
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(map(str, MINIMUM_PYTHON))
        raise SystemExit(
            f"{context} requires Python {required} or later; found "
            f"{platform.python_version()}."
        )
    if platform.python_implementation() != "CPython":
        raise SystemExit(
            f"{context} supports CPython only; found "
            f"{platform.python_implementation()}."
        )
    if sys.flags.optimize:
        raise SystemExit(
            f"{context} must be run without -O or PYTHONOPTIMIZE; "
            "the scientific checks require assertions."
        )
    if not sys.platform.startswith("linux"):
        raise SystemExit(
            f"{context} supports Linux only. It uses Python's Unix-only "
            "resource module and records ru_maxrss with Linux KiB semantics. "
            "Native Windows Python is unsupported; on Windows run the command "
            "inside a WSL2 Linux distribution. macOS/BSD are not claimed by "
            "this release because their resource-accounting semantics and "
            "toolchains were not validated."
        )
    try:
        import resource as resource_module
    except ModuleNotFoundError as exc:  # Defensive: normal Linux CPython has it.
        raise SystemExit(
            f"{context} requires Python's resource module on Linux, but it is "
            "not available in this interpreter."
        ) from exc
    required_names = ("getrusage", "RUSAGE_SELF", "RUSAGE_CHILDREN")
    missing = [name for name in required_names if not hasattr(resource_module, name)]
    if missing:
        raise SystemExit(
            f"{context} requires resource.{', resource.'.join(missing)} on Linux."
        )
    return resource_module


def environment_record(context: str, resource_module: ModuleType | None = None) -> dict[str, object]:
    """Describe the actual validated runtime without fabricating measurements."""
    if resource_module is None:
        resource_module = require_supported_environment(context)
    release = platform.release()
    return {
        "support_status": "supported",
        "supported_platform": "Linux",
        "sys_platform": sys.platform,
        "kernel_release": release,
        "machine": platform.machine(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_optimization_level": sys.flags.optimize,
        "wsl_detected": "microsoft" in release.lower(),
        "resource_accounting": {
            "cpu_time_unit": "seconds",
            "child_cpu_source": "resource.getrusage(RUSAGE_CHILDREN).ru_utime + ru_stime",
            "current_process_cpu_source": "time.process_time()",
            "peak_rss_source": "resource.getrusage(...).ru_maxrss",
            "peak_rss_unit": "KiB on Linux",
            "unsupported_platform_behavior": (
                "fail before execution; no CPU/RSS value is emitted or substituted"
            ),
        },
    }
