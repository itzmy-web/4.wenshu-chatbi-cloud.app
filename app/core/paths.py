from pathlib import Path

# 项目根目录与 SQLite 数据文件路径（云端版数据随包携带）
BASE_DIR = Path(__file__).parents[2]
DATA_DIR = BASE_DIR / "data"
META_DB_PATH = DATA_DIR / "meta.db"
DW_DB_PATH = DATA_DIR / "dw.db"
