#!/usr/bin/env python3
"""生成 samples/data/ 下的演示数据文件（可重复执行）。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)


def write(name: str, text: str, encoding: str):
    (DATA / name).write_bytes(text.encode(encoding) + b"\n")
    print(f"  {name} ({encoding})")


def prod_line(code, name, rate, dt, st) -> bytes:
    nm = name.encode("gbk").ljust(20)
    return code.encode().ljust(8) + nm + rate.encode() + dt.encode() + st.encode()


def main():
    print(f"生成样本文件 → {DATA}")

    # 变长分隔符（GBK），金额隐含 2 位小数；最后一行少一个字段，演示异常提示
    t1 = "\n".join([
        "M00012345|20260101|10050|CNY|00|正常交易",
        "M00067890|20260101|2500000|USD|01|跨境汇款",
        "M00011111|20260102|99|CNY|02|余额不足",
        "M00022222|20260102|88000|CNY|00|刷卡消费",
        "M00033333|20260103|500|CNY|00",
    ])
    write("T1.111.2020.csv", t1, "gbk")

    # 头/体/尾结构（配套 specs/t2-333.yaml + 同名 .head/.tail sidecar spec）
    # 头=首行元信息（3 笔 142.00 与体一致，仅展示不核对）；尾=末行校验行
    t2 = "\n".join([
        "H|0001|202610|3|142.00",
        "M00012345|20261001|10050|CNY|00",
        "M00067890|20261002|3150|CNY|01",
        "M00011111|20261003|1000|USD|02",
        "T|3|142.00|A1B2C3D4",
    ])
    write("T2.333.2026.csv", t2, "gbk")

    # 变长分隔符（UTF-8，分号分隔）
    write("orders_utf8.csv", "\n".join([
        "ORD001;张三;20260101;129900;PAID",
        "ORD002;李四;20260102;8850;PAID",
        "ORD003;王五;20260102;500;FAIL",
    ]), "utf-8")

    # 定长（GBK，44B/行）；最后一行 43B：缺状态字段，演示行长告警
    lines = [
        prod_line("P0000001", "货币基金", "0025000", "20260101", "1"),
        prod_line("P0000002", "债券基金A", "0032500", "20260201", "1"),
        prod_line("P0000003", "混合基金B", "0150000", "20260301", "0"),
        prod_line("P0000009", "货币基金", "0060000", "20260115", ""),
    ]
    (DATA / "prod.222.2026.txt").write_bytes(b"\n".join(lines) + b"\n")
    print(f"  prod.222.2026.txt (gbk, 行长 {[len(x) for x in lines]}B)")

    # JSON Lines（大数金额，演示 parse_float=str 保精度）
    write("orders.jsonl", "\n".join([
        '{"order_id": "O2026010100001", "user": "u1001", "amount": 123456789012345.67, "ccy": "CNY", "status": "PAID"}',
        '{"order_id": "O2026010100002", "user": "u1002", "amount": 99.9, "ccy": "USD", "status": "NEW"}',
        '{"order_id": "O2026010100003", "user": "u1003", "amount": 5, "ccy": "CNY", "status": "FAIL"}',
    ]), "utf-8")

    # 日志内嵌 JSON（含 HTTP 头部上下文）
    write("http_log.txt", "\n".join([
        "2026-01-01 10:00:01 INFO  收到响应",
        "HTTP/1.1 200 OK",
        "Content-Type: application/json",
        "X-Request-Id: req-0001",
        "",
        '{"order_id": "O2026010100001", "amount": 123456789012345.67, "status": "PAID"}',
        "2026-01-01 10:00:02 INFO  处理完成",
        "2026-01-01 10:05:00 INFO  收到响应",
        "HTTP/1.1 400 Bad Request",
        "Content-Type: application/json",
        "",
        '{"err_code": "E400", "message": "金额格式错误"}',
    ]), "utf-8")

    # 与 spec 声明编码不符（spec 说 gbk，实际 utf-8）——演示编码降级
    write("T1.111.2027.csv", "M00090001|20270101|12345|CNY|00|UTF-8编码演示", "utf-8")

    # 无 spec 兜底演示
    write("unknown.dat", "\n".join([
        "A001;张三;20260101;100",
        "A002;李四;20260102;250",
        "A003;王五;20260103;88",
    ]), "utf-8")


if __name__ == "__main__":
    main()
