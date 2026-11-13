---
name: sv
description: 用 sv 在终端解析/美化协议数据文件（定长、分隔符变长、JSON），编写协议 spec（YAML），并按协议反向生成测试数据。当用户需要查看、解析、核对协议文件/对账文件/定长文件/分隔符文件，要求编写或修改协议字段描述（YAML spec），或按协议造样本数据时使用。
---

# sv —— 终端协议文件美化打印

sv 把协议数据文件解析成字段并美化打印到终端。当前版本支持三类**纯文本**协议：
**定长（fixed）**、**变长分隔符（delimited）**、**JSON**。gRPC/RPC/DCC 等二进制协议为二期预留。

入口为 `sv`，与 `python -m structview` 等价；系统装有 runit（Void Linux 核心命令）时 `sv` 可能指向服务管理命令，改用后者。

## 命令速查

```bash
sv read <file>                # 主力：自动识别协议+编码并美化打印
  -p, --proto <spec.yaml>     # 强制走某个协议 spec
  -f, --format fixed|delimited|json|auto   # 强制解析器（无 spec 也能读）
  -d, --delimiter '|'         # 强制分隔符（配合 delimited）
  -e, --encoding gbk|utf-8|gb18030|auto    # 强制编码，覆盖 spec 声明
  -t, --view table|detail|hex # 输出形态，默认 table；detail 看解析值/类型/字节偏移对照
  --raw                       # 不做类型格式化，显示原始值
  --no-color                  # 强制无色输出（也可用 NO_COLOR/FORCE_COLOR 环境变量控制）
  -r, --records 1-5           # 只看指定记录
sv detect <file>              # 诊断：猜测的协议/编码/分隔符/行长，不确定时先跑这个
sv gen --spec s.yaml --count 5 [--out f] [--seed 42] [-e gbk]   # 按协议反向生成数据文件
sv spec check <spec.yaml>     # 校验 spec
sv spec infer <datafile>      # 从数据文件反推草稿 spec（字段名是 colN 占位，需人工补语义）
```

## detail 视图显示约定（-t detail）

每条记录一个字段块，列为 `# / 字段 / 解析值 / 类型 / [偏移]`（偏移列仅定长协议出现）：

```
 #   字段      解析值           类型       偏移
 1   PROD_CD   P0000001(8)      str(8)     [0,8)
 2   PROD_NM   货币基金(8)      str(20)    [8,28)
 3   RATE      0.25000(7)      dec(7,5)   [28,35)
```

- **解析值**：`值(实际字节数)`，按字节计（GBK 汉字 ×2），即该字段在文件中的原始内容大小——枚举等映射字段按原始码计（如 `CNY→人民币(3)`），不是显示值长度；`--raw` 时该列回退为原始串
- **类型**：`str(8)` = 类型(协议字节长度)；dec 追加小数位 `dec(7,5)` = len,小数位；变长/JSON 无协议长度，显示裸类型，仅 dec 显示 `dec(2)`（小数位）；`…尾料`（行溢出内容）不带协议长度
- **偏移**：`[start,end)` 左闭右开字节区间，可对照协议文档逐字段核对切分
- **配色**：解析值默认色、`(字节数)` 与偏移暗淡、类型青色、解析错误红色。色彩控制：终端默认彩色，管道/重定向自动关闭；`NO_COLOR=1`（任意非空值）强制无色——连粗体/暗淡属性也不输出任何 ANSI 转义，适配无法渲染转义序列的终端；`FORCE_COLOR=1` 在管道中强制彩色（配合 `less -R`）；`--no-color` 参数优先级最高

## 协议识别优先级

1. CLI 显式：`--proto` / `--format` / `--delimiter`
2. 项目配置 `.structview/config.yaml` 的 `overrides`（glob → spec，人工显式决定）
3. spec 自带 `match` 模式：扫描 `specs_dir`（默认 `specs/`、`.structview/specs/`），文件名命中即用
4. 内容启发式：整体/逐行/内嵌 JSON → 行字节长一致→定长 → 分隔符频率一致（`| \t ; , ^ ~`）→ 兜底表格

## spec 编写规范

spec 是 YAML 文件，协议变更 = 改 spec，改完立即生效（零编译）。

### 顶层键

| 键 | 必填 | 说明 |
|---|---|---|
| name | 否 | 协议名，打印在表头 |
| match | 建议 | 文件名 glob 列表，如 `["T1.111.*.csv"]`，供自动识别 |
| format | **是** | `fixed` / `delimited` / `json` |
| encoding | 建议 | spec 声明的文件编码：`gbk` / `gb18030` / `utf-8` / `big5` / `auto`（缺省 auto） |
| delimiter | delimited 必填 | 分隔符；多字符分隔符不走引号规则 |
| quote | 否 | 引号字符，缺省 `"`；设为 null 关闭引号规则 |
| escape | 否 | 转义字符 |
| record_len | fixed 可选 | 每行记录字节数；缺省按字段 len 合计，不一致会告警 |
| fields | fixed/delimited 必填 | 字段列表 |

### 字段键

| 键 | 说明 |
|---|---|
| name | 字段名（必填） |
| type | `str`/`int`/`dec`/`date`/`time`/`hex`/`enum`；**不写或写未知类型一律按 str 兜底** |
| len | fixed 必填，**按字节**（GBK 一个汉字占 2 字节） |
| fmt | date/time 的输入格式（strptime），缺省 `%Y%m%d` / `%H%M%S`；输出统一 `2026-01-01` / `09:30:00` |
| scale | dec 的隐含小数位数：原始 `10050` + scale 2 → 显示 `100.50`；原始带小数点则直接解析 |
| map | enum 的取值映射，**键加引号**：`{"00": 成功}`（不加引号 YAML 会把 00 解析成整数 0） |
| encoding | 字段级编码覆盖（混编码文件预留） |
| sample | gen 用的取值池：`sample: [A001, A002, A003]` |

### 完整示例

变长分隔符（T1 对账文件）：

```yaml
name: T1 对账文件
match: ["T1.111.*.csv"]
encoding: gbk
format: delimited
delimiter: "|"
fields:
  - {name: 商户号,   type: str}
  - {name: 交易日期, type: date, fmt: "%Y%m%d"}
  - {name: 交易金额, type: dec,  scale: 2}
  - {name: 币种,     type: enum, map: {CNY: 人民币, USD: 美元}}
  - {name: 状态,     type: enum, map: {"00": 成功, "01": 待清算, "02": 失败}}
  - {name: 备注,     type: str}
```

定长（产品表文件）：

```yaml
name: 产品表文件
match: ["prod.222.*.txt"]
encoding: gbk
format: fixed
record_len: 44
fields:
  - {name: PROD_CD, len: 8,  type: str}
  - {name: PROD_NM, len: 20, type: str}     # 20 字节 ≈ 10 个汉字
  - {name: RATE,    len: 7,  type: dec, scale: 5}
  - {name: EFF_DT,  len: 8,  type: date, fmt: "%Y%m%d"}
  - {name: ST,      len: 1,  type: enum, map: {"1": 正常, "0": 停售}}
```

## 硬规则（违反会导致解析错误）

1. **len 单位是字节，不是字符**。GBK 下汉字占 2 字节：`货币基金` = 8 字节。写 spec 前先确认编码，再用字节数算 len。工具校验 `record_len` 与字段合计是否一致。
2. **定长数值右对齐补 0，文本左对齐补空格**（生成时的约定，解析时自动 trim）。
3. **dec 的 scale 是隐含小数位**：协议写"金额 12 位，末 2 位是小数"就是 `{len: 12, type: dec, scale: 2}`，原始数据里通常没有小数点。
4. **enum 的 map 键一律加引号**，尤其是 `{"00": ...}` 这类前导零编码。
5. **encoding 必须与文件实际编码一致**；拿不准时先 `sv detect`。spec 声明的编码解码失败会自动降级探测，但 GBK 文件被声明成 gbk 而实际是 utf-8 时可能解码"成功"但显示乱码——看到疑似乱码就用 `-e utf-8` 验证。
6. 日期 fmt 用 Python strptime 语法：`%Y%m%d`、`%Y-%m-%d`、`%Y%m%d%H%M%S`。

## 按协议生成数据文件（sv gen）

```bash
sv gen --spec specs/prod-222.yaml --count 5 --seed 42 --out sample.txt
```

- 按字段类型生成：str→随机大写字母数字（按 len 截断）；int/dec→范围随机（隐含小数位）；date→近一年随机；time→随机时刻；enum→从 map 键随机；hex→随机十六进制
- 字段写 `sample: [...]` 时只从取值池里选
- `--seed` 保证可复现；`-e` 覆盖生成编码
- 生成后**自动回读校验**（用对应解码器解析一遍），stderr 会报告"字段解析全部正常 / N 个异常"
- 用途：给下游系统造测试数据、验证 spec 本身写得对不对

## 从数据文件反推 spec（sv spec infer）

```bash
sv spec infer T1.111.2020.csv > specs/t1-111-draft.yaml
```

- 自动推断：编码、分隔符、字段数、各列类型（日期/整数/小数/疑似枚举会给出猜测注释）
- **字段名一律是 col1..N 占位**，类型猜测也只是启发式——必须人工（或结合协议文档）核对后再用
- 定长文件只能推断总行长，字段边界无法从数据推断，草稿里是单字段 + 注释提示补 len

## 标准工作流（拿到一个新协议时）

1. **读协议文档**，确认：编码、记录切分方式（定长/分隔符）、字段表（名称/长度/类型/小数位/枚举值）
2. **写 spec** 到 `specs/` 目录，`match` 写上文件名规律
3. **校验**：`sv spec check specs/xxx.yaml`
4. **造样本**：`sv gen --spec specs/xxx.yaml --count 5 --seed 1 --out /tmp/t.txt` —— 回读校验通过说明 spec 自洽
5. **解析真实文件**：`sv read 实际文件`（按 match 自动匹配）；字段对不齐时用 `-t detail` 看类型、字节偏移 `[start,end)` 与解析值+实际字节数，对照协议文档修 spec
6. 协议变更时：只改 spec 的 `fields`，无需动任何代码

## 何时用强制参数

| 场景 | 用法 |
|---|---|
| 文件名与 spec 的 match 冲突 | `sv read f -p 正确的spec.yaml` |
| spec 声明的编码不对/想试其它编码 | `-e gbk` / `-e utf-8` / `-e auto` |
| 没写 spec，只想快速看分隔符文件 | `sv read f -f delimited -d '|'` |
| 怀疑识别结果 | 先 `sv detect f` 看诊断 |
| 只想看原始字节 | `-t hex`；只看原始值不做类型格式化 `--raw` |
| 终端不支持色彩 / 输出到管道 | 管道默认自动无色；`NO_COLOR=1` 强制无色，`FORCE_COLOR=1` 管道中强制彩色（`--no-color` 优先级最高） |

## 当前版本限制

- 引号字段内含换行的 CSV 不支持（协议文件中罕见；引号内含分隔符/转义引号支持）
- `key_field`/`layouts`（多记录类型分叉）为预留功能，声明了会告警并按主布局解析
- 定长 binary 模式（无换行、按记录长切）、gRPC/RPC（protobuf 动态解码）、DCC 均为二期预留
- 单文件设计目标 ≤1000 行记录
