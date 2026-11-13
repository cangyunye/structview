# structview（`sv`）

Linux 终端下的协议文件美化打印工具。把协议数据文件解析成字段，用 rich 渲染成表格/详情视图。

当前支持三类**纯文本**协议（gRPC/RPC/DCC 等二进制协议为二期预留，解码器接口已留好）：

- **定长（fixed）**：按字节切片，支持 GBK 中文（len 按字节）、隐含小数、日期、枚举
- **变长分隔符（delimited）**：单字符分隔符走 CSV 引号规则，多字符走普通切分
- **JSON**：整体 JSON / JSON Lines / 日志内嵌 JSON（自动提取并展示 HTTP 头部上下文），浮点按字符串保精度

核心设计：**协议描述（YAML spec）驱动**。协议变更 = 改 spec，改完即生效，零编译。

## 安装

```bash
python3 -m venv .venv --copies   # 外置卷/不支持符号链接的文件系统加 --copies
.venv/bin/pip install -e .
# 或 pipx install .
```

安装后有两个等价入口：console script `sv` 和 `python -m structview`。

> **命令名冲突**：`sv` 与 runit 服务管理命令同名——Void Linux 出厂自带，Debian/Ubuntu 的 `runit` 包、Alpine/Arch 的可选包也提供 `/usr/bin/sv`；Windows 与 macOS 默认无冲突。venv（`.venv/bin`）和 pipx（`~/.local/bin`）的安装路径排在 PATH 前面，交互终端里本工具优先；若 `command -v sv` 指向 `/usr/bin/sv`（runit 版）或在 cron/sudo 等受限环境运行，改用 `python -m structview`。

## 快速上手

```bash
sv read samples/data/T1.111.2020.csv        # 按 specs/*.yaml 的 match 自动匹配
sv read samples/data/prod.222.2026.txt -t detail   # 定长详情视图（类型/偏移/解析值+实际字节）
cat resp.json | sv read -                   # stdin
sv detect unknown.dat                       # 识别诊断
sv gen --spec specs/prod-222.yaml --count 5 --seed 42 --out /tmp/t.txt   # 反向造数据
sv spec check specs/t1-111.yaml             # 校验 spec
sv spec infer unknown.dat                   # 从数据反推草稿 spec
```

`-t detail` 视图约定：类型列 `str(8)` = 类型(协议字节长度)，dec 显示 `dec(7,5)`（len,小数位）；偏移列 `[0,8)` 左闭右开字节区间；解析值 `3000(4)` = 值(文件中实际字节数)。色彩开关：终端默认彩色，管道/重定向自动关闭；`NO_COLOR=1` 强制无色（含粗体等属性），`FORCE_COLOR=1` 在管道中强制彩色，`--no-color` 参数优先级最高。

## 协议识别优先级

1. CLI 显式（`--proto` / `--format` / `--delimiter` / `--encoding`）
2. `.structview/config.yaml` 的 `overrides`（glob → spec）
3. spec 自带 `match` 文件名模式（扫描 `specs_dir`，默认 `specs/`）
4. 内容启发式（JSON → 定长 → 分隔符 → 兜底表格）

编码：spec 声明（`encoding: gbk` 等）优先，CLI `-e` 可强制覆盖；auto 链为 BOM → utf-8 → gb18030 → latin-1。

## spec 编写

完整规范、硬规则（len 按字节、enum 键加引号等）与工作流见 [skills/sv/SKILL.md](skills/sv/SKILL.md)（该文件同时是给 AI agent 用的 skill，可直接放入 `~/.agents/skills/` 或项目 `.zcode/skills/`）。

示例 spec 在 `specs/`，样本数据由 `python3 samples/make_samples.py` 生成。

## 测试

```bash
.venv/bin/python -m pytest
```
