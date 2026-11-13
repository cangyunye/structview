"""python -m structview 后备入口，与 console script `sv` 等价。

命令名冲突时（Void Linux 核心命令 / Debian、Ubuntu 的 runit 包也提供 `sv`）
用它绕开，不受 PATH 中 runit 的 `/usr/bin/sv` 影响。
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
