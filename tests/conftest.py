import pathlib
import sys

# 未安装包时也可直接跑 pytest（已安装则该路径无害）
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
