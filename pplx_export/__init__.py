"""pplx_export — a conversation export framework (ships with a built-in Perplexity adapter).

Layout:
  config.py   Centralized configuration (account registry, site constants, default paths)
  core/       Domain models, errors, throttling, dual-channel transports, credentials,
              checkpoints, relation graph, registry
  sites/      SiteAdapter interface and per-site adapters (perplexity built in)
  writers/    Output persistence abstraction (web_archive layout implemented in
              sites/perplexity/fs_writer.py)
  hooks/      Hook system (incremental capture, relation maintenance, periodic scheduling)
  cli.py      pplx-export CLI entry; ask_cli.py pplx-ask CLI entry

Design principle: retain raw data (raw JSON) alongside rendered artifacts so
rendering can be replayed offline; parsing is decoupled from site structure so
the exporter tolerates upstream data-schema changes.

pplx_export — 对话导出框架（内置 Perplexity 站点适配器）。

分层结构：
  config.py   集中配置（账户表、站点常量、默认路径）
  core/       领域模型、错误、限频、双通道 transport、凭证、断点、关系图、注册表
  sites/      SiteAdapter 接口与各站点适配（perplexity 内置）
  writers/    输出落盘抽象（web_archive 布局实现见 sites/perplexity/fs_writer.py）
  hooks/      Hook 系统（增量捕获、关系维护、周期调度）
  cli.py      pplx-export 命令行入口；ask_cli.py pplx-ask 命令行入口

设计原则：原始数据（raw JSON）与渲染产物一并保留，可离线重渲；解析与站点结构
解耦，抗数据结构变更。
"""

from .core.registry import register as _register

__version__ = "0.1.0"


def _register_builtin():
    """Register the built-in site adapters (sites are pluggable: new sites register here).

    内建站点适配器注册（站点可插拔：新增站点在此登记）。
    """
    from .sites.perplexity.adapter import PerplexityAdapter
    _register("perplexity", PerplexityAdapter)


_register_builtin()
