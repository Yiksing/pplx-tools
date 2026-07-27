"""Atomic filesystem writes: one write semantic, one implementation.

Archive products (thread.json / raw_*.json / rendered markdown / manifests)
must never be left half-written by a killed process or a full disk: a
truncated thread.json fails the V5-03 identity check and detaches the
directory from auto-migration, and a truncated raw file loses the highest
source of truth. This helper applies the same temp-file + os.replace pattern
already established by BatchState.save / CookieCache.save /
init_cmd.write_config / translate_docs._write_text_atomic.

The temp file lives in the target's directory under the hidden deterministic
name ``.{name}.tmp``: os.replace never crosses filesystems, no existing glob
(``*/*/*/thread.json``, ``turn_*.md`` …) can pick it up, and a crash residue
is simply reused and replaced by the next write of the same target — no
cleanup logic needed. No fsync (same trade-off as BatchState.save): the
guarantee is "no truncated target on process kill / disk full"; power-loss
durability is out of scope.

原子写盘：一个写语义，一个实现。

归档产物（thread.json / raw_*.json / 渲染 markdown / manifest）绝不允许被
进程中断或磁盘满留下半成品：截断的 thread.json 会使 V5-03 身份核验拒认目录、
脱离自动迁移，截断的 raw 文件直接损失最高真源层。本助手沿用 BatchState.save /
CookieCache.save / init_cmd.write_config / translate_docs._write_text_atomic
已确立的临时文件 + os.replace 模式。

临时文件位于目标同目录的隐藏确定性名 ``.{name}.tmp``：os.replace 不跨文件
系统，任何现有 glob（``*/*/*/thread.json``、``turn_*.md`` 等）都不会误捕，
崩溃残留会被下次同目标写入直接复用覆盖——无需清理逻辑。不做 fsync
（与 BatchState.save 同取舍）：保证的是「进程被杀/磁盘满不留截断目标」，
掉电持久性不在范围内。
"""

from __future__ import annotations

import os
from pathlib import Path


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text atomically: hidden same-directory temp file, then os.replace.

    Creates parent directories as needed; on any failure before the final
    replace, the pre-existing target stays byte-identical.

    原子写文本：同目录隐藏临时文件写毕后 os.replace 替换目标。

    需要时自建父目录；最终替换前的任何失败都保持既有目标字节不变。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)
