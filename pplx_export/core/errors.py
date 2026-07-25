"""Error types.

错误类型。"""


class PplxExportError(Exception):
    """Base error of the framework.

    框架基础错误。"""


class AuthError(PplxExportError):
    """Credential acquisition/refresh failure.

    凭证获取/刷新失败。"""


class RateLimitError(PplxExportError):
    """Rate limited (429); backoff required. 401/403 are auth failures, see AuthTransportError.

    触发限流（429），需退避。401/403 属鉴权失败，见 AuthTransportError。"""


class EntryExpiredError(PplxExportError):
    """Thread purged by the platform (ENTRY_EXPIRED). Terminal, unrecoverable, do not retry.

    线程已被平台清除（ENTRY_EXPIRED）。终态，不可恢复，不应重试。"""


class EntryDeletedError(EntryExpiredError):
    """Thread actively deleted by the user/remote side (ENTRY_DELETED, HTTP 400 "This entry has been
    deleted", the downstream effect of the delete endpoint
    DELETE /rest/thread/delete_thread_by_entry_uuid).
    Terminal, unrecoverable, do not retry.

    Rationale for inheriting EntryExpiredError: both are the same "thread no longer exists"
    terminal state — existing paths unaware of ENTRY_DELETED (only `except EntryExpiredError`)
    treat it as expired and fall back to a terminal state, never into "retrying a transient
    error forever"; aware paths (batch/export/sync-deleted/search-mode-backfill) catch this
    subclass first and classify precisely with deleted semantics (batch_state terminal
    statuses deleted and expired side by side). Note: `except EntryDeletedError` must come
    before EntryExpiredError.

    线程已被用户/远端主动删除（ENTRY_DELETED，HTTP 400 "This entry has been
    deleted"，删除端点 DELETE /rest/thread/delete_thread_by_entry_uuid 的下游表现）。
    终态，不可恢复，不应重试。

    继承 EntryExpiredError 的理由：二者同为「线程已不存在」终态——未感知
    ENTRY_DELETED 的既有路径（只 except EntryExpiredError）会把它当 expired
    兜底为终态，绝不落入「瞬态错误永久重试」；感知它的路径（batch/export/
    sync-deleted/search-mode-backfill）先捕获本子类，按 deleted 语义精确分类
    （batch_state 终态 deleted 与 expired 并列）。注意除 EntryDeletedError
    必须先于 EntryExpiredError。"""


class SchemaError(PplxExportError):
    """Data structure does not match expectations (site redesign). Log only; degrade gracefully where possible.

    数据结构不符合预期（站点改版）。仅记录，尽量优雅降级。"""


class TransportError(PplxExportError):
    """Transport-layer request failure.

    transport 层请求失败。"""


class AuthTransportError(TransportError):
    """Authentication failure (401/403): fail immediately, no backoff retry. batch should fail-fast after several consecutive triggers.

    鉴权失败（401/403）：立即失败，不退避重试。batch 连续多次触发时应 fail-fast。"""
