"""Central logging: leveled console output + optional full file logging.

Usage:
  from .logging import get_logger
  log = get_logger(__name__)
  log.info("progress") / log.debug("details") / log.warning("alert")

console: verbosity=0 → INFO (user progress); ≥1 → DEBUG (request tracing/internal decisions).
file: enabled only when setup_logging is given log_file; always full DEBUG.

中央日志：console 分级 + 可选文件全量落盘。

用法：
  from .logging import get_logger
  log = get_logger(__name__)
  log.info("进度") / log.debug("细节") / log.warning("告警")

console：verbosity=0 → INFO（用户进度）；≥1 → DEBUG（请求追踪/内部判定）。
file：仅 setup_logging 指定 log_file 时启用，始终 DEBUG 全量。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

_ROOT_NAME = "pplx_export"
_configured = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


class _ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%H:%M:%S")
        msg = record.getMessage()
        if record.levelno >= logging.WARNING:
            return f"{ts} [{record.levelname}] {msg}"
        return f"{ts} {msg}"


def setup_logging(verbosity: int = 0, log_file: Path | None = None) -> logging.Logger:
    """Initialize the root logger (idempotent; repeated calls only adjust level / add a file handler).

    初始化根 logger（幂等，重复调用只调级别/加文件 handler）。"""
    global _configured
    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(logging.DEBUG)
    root.propagate = False

    console_level = logging.DEBUG if verbosity >= 1 else logging.INFO
    if not _configured:
        ch = logging.StreamHandler()
        ch.setFormatter(_ConsoleFormatter())
        root.addHandler(ch)
        _configured = True
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(console_level)

    if log_file is not None and not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(fh)
        root.info(f"[log] 日志文件: {log_file}")
    return root
