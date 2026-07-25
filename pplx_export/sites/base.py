"""SiteAdapter abstraction: the site-agnostic conversation export interface.

Any site (Perplexity or another conversation platform) implements this interface
and registers via core.registry to reuse the core layer (throttling, checkpoint
resume, filesystem writing, relation graph, hooks).

SiteAdapter 抽象：站点无关的对话导出接口。

任何站点（Perplexity、其他对话平台）实现本接口并经 core.registry 注册后，
即可复用核心层（限频、断点续跑、写盘、关系图、Hook）。
"""

from __future__ import annotations

import abc
from typing import Iterator, Optional

from ..core.models import Account, Conversation, RelationEdge


class SiteAdapter(abc.ABC):
    """Abstract base class for site adapters.

    站点适配器抽象基类。
    """

    #: Site identifier (used for directories/registration).
    #: 站点标识（用于目录/注册）
    site_id: str = "abstract"

    @abc.abstractmethod
    def list_threads(self, account: Account, **kwargs) -> Iterator[dict]:
        """List an index of all conversations of the account (lightweight metadata dict with uuid/title/mode/lastUpdated/space, etc.).

        列出账户全部对话的索引（轻量元数据 dict，含 uuid/title/mode/lastUpdated/space 等）。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_thread(self, uuid: str, **kwargs) -> Conversation:
        """Fetch the full structure of one conversation (turns/steps/citations/sub-agents) and return a Conversation.

        抓取单个对话的完整结构（轮次/步骤/引文/子代理），返回 Conversation。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_report(self, conversation: Conversation, **kwargs) -> Optional[str]:
        """Fetch the markdown content of report-type artifacts (deep-research reports); None when absent.

        抓取报告类产物（deep-research 报告）的 markdown 内容。无则返回 None。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_assets(self, conversation: Conversation, **kwargs) -> list:
        """Fetch conversation assets (versioned files); returns a list of Asset (with download destinations).

        抓取对话的资产（版本化文件）。返回 Asset 列表（含下载落点）。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def relations(self, conversation: Conversation) -> list[RelationEdge]:
        """Extract relation edges between this conversation and other conversations.

        提取对话与其他对话的关系边。
        """
        return []
