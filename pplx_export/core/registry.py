"""SiteAdapter registry: pluggable sites.

SiteAdapter 注册表：站点可插拔。"""

from __future__ import annotations

from ..sites.base import SiteAdapter

_REGISTRY: dict[str, type[SiteAdapter]] = {}


def register(site_id: str, adapter_cls: type[SiteAdapter]):
    _REGISTRY[site_id] = adapter_cls


def get_adapter(site_id: str, **kwargs) -> SiteAdapter:
    if site_id not in _REGISTRY:
        raise KeyError(f"未注册的站点适配器: {site_id}")
    return _REGISTRY[site_id](**kwargs)


def registered_sites() -> list[str]:
    return sorted(_REGISTRY)
