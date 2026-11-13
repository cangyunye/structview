"""gRPC/RPC（protobuf）解码器 —— 二期预留占位。

规划方案：
- 输入为 protoc --include_imports --descriptor_set_out=svc.pb 产出的描述集，
  用 google.protobuf descriptor_pool + MessageFactory 动态解码，不生成任何代码；
- gRPC 帧需先剥掉帧头（1 字节压缩标志 + 4 字节长度前缀）；
- 未知字段按原始 varint/bytes 展示。

接口签名与其它解码器一致，二期实现后在此注册：
    parse(data: bytes, spec, encoding: str, *, delimiter=None, raw_mode=False) -> ParseResult
"""

from __future__ import annotations


def parse(data: bytes, spec, encoding: str, *, delimiter=None, raw_mode=False):
    raise NotImplementedError(
        "proto 解码为二期预留功能，当前版本仅支持 fixed/delimited/json 纯文本协议"
    )
