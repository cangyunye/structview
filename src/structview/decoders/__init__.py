"""解码器注册表。

二期在此注册 proto（gRPC/RPC）与 DCC 等自定义解码器，接口签名：
    parse(data: bytes, spec, encoding: str, *, delimiter=None, raw_mode=False) -> ParseResult
"""

from __future__ import annotations

from typing import Callable

_REGISTRY: dict[str, Callable] = {}


def register(name: str):
    def deco(fn):
        _REGISTRY[name] = fn
        return fn
    return deco


def get_decoder(name: str) -> Callable:
    if name not in _REGISTRY:
        raise KeyError(f"未注册的解码器: {name}（可用: {', '.join(sorted(_REGISTRY))}）")
    return _REGISTRY[name]


def available() -> list[str]:
    return sorted(_REGISTRY)


# 注册内置解码器
from . import fixed, delimited, jsondec  # noqa: E402,F401
