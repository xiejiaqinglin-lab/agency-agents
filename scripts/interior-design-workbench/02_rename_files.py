"""
文件批量重命名工具
================
将 99_临时收件箱\待分类 中的文件按规范重命名。

命名格式：[YYYYMMDD]_[客户名]_[文件类型]_[说明].扩展名
示例：    20240315_王先生_效果图_客厅.jpg

使用方法：
  python 02_rename_files.py

依赖：Python 3.8+，无需额外安装包
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime


# ── 配置区（按需修改）─────────────────────────────────────────
INBOX_DIR = Path(r"D:\AI_System\99_临时收件箱\待分类")

# 按扩展名推断文件类型（用于自动建议）
EXT_TYPE_MAP = {
    ".dwg": "CAD图纸",
    ".dxf": "CAD图纸",
    ".skp": "模型",
    ".pdf": "文件",
    ".docx": "文件",
    ".doc": "文件",
    ".xlsx": "报价单",
    ".xls": "报价单",
    ".jpg": "图片",
    ".jpeg": "图片",
    ".png": "图片",
    ".mp4": "视频",
    ".mov": "视频",
    ".heic": "图片",
}

# 常用文件类型快捷选项
FILE_TYPES = [
    "效果图", "户型图", "CAD图纸", "施工现场",
    "合同", "报价单", "灵感图", "材料样品",
    "沟通记录", "验收照片", "视频", "其他"
]
# ─────────────────────────────────────────────────────────────


def get_file_date(path: Path) -> str:
    """用文件修改时间作为默认日期。"""
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime).strftime("%Y%m%d")


def ask(prompt: str, default: str = "") -> str:
    """显示提示并读取用户输入，回车使用默认值。"""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def pick_from_list(options: list, prompt: str) -> str:
    """展示编号列表，用户输入编号选择。"""
    for i, opt in enumerate(options, 1):
        print(f"  {i:2d}. {opt}")
    while True:
        choice = input(f"{prompt} (输入编号或直接输入内容): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        elif choice:
            return choice
        print("  请输入有效的编号或内容。")


def rename_file(file: Path) -> None:
    """交互式重命名单个文件。"""
    print(f"\n{'─'*50}")
    print(f"当前文件：{file.name}  ({file.stat().st_size // 1024} KB)")
    print(f"{'─'*50}")

    # 跳过选项
    skip = input("  [Enter] 开始重命名  [s] 跳过  [q] 退出: ").strip().lower()
    if skip == "q":
        raise SystemExit("用户退出。")
    if skip == "s":
        print("  → 已跳过")
        return

    # 日期
    default_date = get_file_date(file)
    date_str = ask("  日期 (YYYYMMDD)", default_date)

    # 客户名
    client = ask("  客户名 (如：王先生 / 李总 / Johnson)").strip()
    if not client:
        print("  → 客户名不能为空，已跳过")
        return

    # 文件类型
    print("  文件类型：")
    suggested = EXT_TYPE_MAP.get(file.suffix.lower(), "")
    if suggested:
        print(f"  (建议：{suggested})")
    file_type = pick_from_list(FILE_TYPES, "  选择文件类型")

    # 说明（可选）
    note = ask("  补充说明 (可选，如：客厅/v2/已签)", "").strip()

    # 组合新文件名
    parts = [date_str, client, file_type]
    if note:
        parts.append(note)
    new_name = "_".join(parts) + file.suffix.lower()
    new_path = file.parent / new_name

    # 冲突处理
    if new_path.exists():
        new_name = "_".join(parts) + "_1" + file.suffix.lower()
        new_path = file.parent / new_name
        print(f"  ⚠ 文件名冲突，自动添加后缀：{new_name}")

    # 确认
    print(f"\n  旧文件名：{file.name}")
    print(f"  新文件名：{new_name}")
    confirm = input("  确认重命名？[Y/n]: ").strip().lower()
    if confirm in ("", "y", "yes"):
        file.rename(new_path)
        print(f"  ✓ 已重命名")
    else:
        print("  → 已取消")


def main():
    print("=" * 50)
    print(" 文件批量重命名工具")
    print("=" * 50)
    print(f"\n收件箱路径：{INBOX_DIR}")

    if not INBOX_DIR.exists():
        print(f"\n❌ 路径不存在：{INBOX_DIR}")
        print("  请先运行 01_setup_folders.bat 创建目录结构")
        input("\n按 Enter 退出...")
        sys.exit(1)

    files = sorted([f for f in INBOX_DIR.iterdir() if f.is_file()])

    if not files:
        print("\n✓ 收件箱为空，无需处理。")
        input("\n按 Enter 退出...")
        return

    print(f"\n找到 {len(files)} 个文件待处理：")
    for f in files:
        size_kb = f.stat().st_size // 1024
        print(f"  · {f.name} ({size_kb} KB)")

    print()
    input("按 Enter 开始逐个处理（输入 q 可随时退出）...")

    renamed = 0
    skipped = 0

    try:
        for file in files:
            try:
                before = file.name
                rename_file(file)
                if not file.exists():  # 文件已被重命名
                    renamed += 1
                else:
                    skipped += 1
            except SystemExit:
                break
            except Exception as e:
                print(f"  ❌ 处理出错：{e}")
                skipped += 1
    except KeyboardInterrupt:
        print("\n\n用户中断。")

    print(f"\n{'='*50}")
    print(f" 完成：重命名 {renamed} 个，跳过 {skipped} 个")
    print(f"{'='*50}")
    input("\n按 Enter 退出...")


if __name__ == "__main__":
    main()
