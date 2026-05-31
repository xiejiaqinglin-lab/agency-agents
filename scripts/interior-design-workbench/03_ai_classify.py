"""
AI 图片自动分类工具
==================
扫描 99_临时收件箱 中的图片，调用 Claude API 识别内容，
自动建议归档路径，由用户确认后移动文件。

使用方法：
  1. 安装依赖：pip install anthropic pillow
  2. 设置环境变量：set ANTHROPIC_API_KEY=你的密钥
  3. 运行：python 03_ai_classify.py

依赖：Python 3.8+、anthropic、pillow
"""

import os
import sys
import base64
import shutil
from pathlib import Path
from datetime import datetime

try:
    import anthropic
except ImportError:
    print("❌ 缺少依赖，请先运行：pip install anthropic")
    sys.exit(1)

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ── 配置区（按需修改）─────────────────────────────────────────
ROOT_DIR   = Path(r"D:\AI_System")
INBOX_DIR  = ROOT_DIR / "99_临时收件箱"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp"}

# 目标文件夹映射（AI 分类结果 → 实际路径）
# 留空表示路径中的客户名需要用户手动确认
CATEGORY_PATHS = {
    "户型图":     "01_客户项目/{client}/01_户型图",
    "效果图":     "01_客户项目/{client}/03_效果图",
    "CAD截图":    "01_客户项目/{client}/02_CAD图纸",
    "施工现场":   "01_客户项目/{client}/04_施工现场",
    "合同":       "01_客户项目/{client}/05_合同报价",
    "报价单":     "01_客户项目/{client}/05_合同报价",
    "灵感图":     "06_素材库/灵感图",
    "材料样品":   "06_素材库/材料样品",
    "品牌素材":   "06_素材库/品牌素材",
    "沟通记录":   "01_客户项目/{client}/00_沟通记录",
    "验收照片":   "01_客户项目/{client}/06_验收交付",
    "家庭照片":   "04_家庭成长/家庭照片",
    "其他":       "99_临时收件箱/待分类",
}

# 已知客户列表（运行时动态读取客户项目目录）
def get_known_clients() -> list:
    client_dir = ROOT_DIR / "01_客户项目"
    if not client_dir.exists():
        return []
    return [d.name for d in client_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
# ─────────────────────────────────────────────────────────────


def encode_image(path: Path) -> tuple[str, str]:
    """将图片转为 base64 并返回 (base64字符串, media_type)。"""
    ext = path.suffix.lower()
    media_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    media_type = media_map.get(ext, "image/jpeg")

    # HEIC 需要转换
    if ext == ".heic":
        if not PIL_AVAILABLE:
            raise ValueError("HEIC 格式需要安装 pillow：pip install pillow")
        img = Image.open(path)
        import io
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG")
        data = base64.standard_b64encode(buf.getvalue()).decode()
        return data, "image/jpeg"

    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    return data, media_type


def classify_image(client: anthropic.Anthropic, image_path: Path) -> dict:
    """调用 Claude 识别图片类型，返回分类结果。"""
    data, media_type = encode_image(image_path)

    categories = list(CATEGORY_PATHS.keys())

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # 用 Haiku 降低成本
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": data,
                    },
                },
                {
                    "type": "text",
                    "text": f"""你是一个室内设计行业的文件分类助手。
请分析这张图片，判断它属于以下哪个类别：
{chr(10).join(f'- {c}' for c in categories)}

请用以下 JSON 格式回答（只输出 JSON，不要其他内容）：
{{
  "category": "类别名称",
  "confidence": "高/中/低",
  "description": "一句话描述图片内容（中文，不超过20字）"
}}"""
                }
            ],
        }],
    )

    import json
    text = response.content[0].text.strip()
    # 清理可能的 markdown 代码块
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def pick_client(known_clients: list) -> str:
    """让用户选择或输入客户名。"""
    if known_clients:
        print("  已知客户项目：")
        for i, c in enumerate(known_clients, 1):
            print(f"    {i:2d}. {c}")
        print(f"  (直接输入新客户名，或输入编号选择已有客户)")
        choice = input("  客户名: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(known_clients):
            return known_clients[int(choice) - 1]
        return choice
    return input("  客户名: ").strip()


def process_image(ai_client: anthropic.Anthropic, image_path: Path, known_clients: list) -> bool:
    """处理单张图片：分类 → 确认 → 移动。"""
    print(f"\n{'─'*55}")
    print(f"图片：{image_path.name}  ({image_path.stat().st_size // 1024} KB)")

    skip = input("  [Enter] 开始分析  [s] 跳过  [q] 退出: ").strip().lower()
    if skip == "q":
        raise SystemExit
    if skip == "s":
        print("  → 已跳过")
        return False

    print("  🤖 正在识别...")
    try:
        result = classify_image(ai_client, image_path)
    except Exception as e:
        print(f"  ❌ 识别失败：{e}")
        return False

    category    = result.get("category", "其他")
    confidence  = result.get("confidence", "低")
    description = result.get("description", "")

    print(f"\n  识别结果：{category}（置信度：{confidence}）")
    if description:
        print(f"  内容描述：{description}")

    # 确认类别
    confirm_cat = input(f"  使用此分类？[Y/n] 或输入新类别: ").strip()
    if confirm_cat.lower() in ("n", "no"):
        print("  可选类别：" + " / ".join(CATEGORY_PATHS.keys()))
        category = input("  请输入类别: ").strip()
    elif confirm_cat and confirm_cat.lower() not in ("y", "yes", ""):
        category = confirm_cat

    # 获取目标路径模板
    path_template = CATEGORY_PATHS.get(category, CATEGORY_PATHS["其他"])

    # 是否需要客户名
    client_name = ""
    if "{client}" in path_template:
        print(f"\n  归档到客户项目下，请选择客户：")
        client_name = pick_client(known_clients)
        if not client_name:
            print("  → 客户名为空，已跳过")
            return False
        path_template = path_template.replace("{client}", client_name)

    dest_dir = ROOT_DIR / path_template
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 建议文件名
    date_str   = datetime.fromtimestamp(image_path.stat().st_mtime).strftime("%Y%m%d")
    clean_name = client_name if client_name else "素材"
    new_name   = f"{date_str}_{clean_name}_{category}{image_path.suffix.lower()}"
    dest_path  = dest_dir / new_name

    # 冲突处理
    counter = 1
    while dest_path.exists():
        new_name  = f"{date_str}_{clean_name}_{category}_{counter}{image_path.suffix.lower()}"
        dest_path = dest_dir / new_name
        counter  += 1

    print(f"\n  目标路径：{dest_path}")
    confirm_move = input("  确认移动？[Y/n]: ").strip().lower()
    if confirm_move in ("", "y", "yes"):
        shutil.move(str(image_path), str(dest_path))
        print(f"  ✓ 已移动")
        return True
    else:
        print("  → 已取消")
        return False


def main():
    print("=" * 55)
    print(" AI 图片自动分类工具")
    print("=" * 55)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("\n❌ 未设置 API Key")
        print("  请运行：set ANTHROPIC_API_KEY=你的密钥")
        print("  然后重新运行此脚本")
        input("\n按 Enter 退出...")
        sys.exit(1)

    if not INBOX_DIR.exists():
        print(f"\n❌ 收件箱路径不存在：{INBOX_DIR}")
        print("  请先运行 01_setup_folders.bat")
        input("\n按 Enter 退出...")
        sys.exit(1)

    # 收集所有图片（递归扫描收件箱）
    images = sorted([
        f for f in INBOX_DIR.rglob("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS
    ])

    if not images:
        print("\n✓ 收件箱中没有图片文件。")
        input("\n按 Enter 退出...")
        return

    known_clients = get_known_clients()
    print(f"\n找到 {len(images)} 张图片，已知客户 {len(known_clients)} 个")
    print(f"收件箱：{INBOX_DIR}")
    print()
    input("按 Enter 开始处理（每张图片单独确认，输入 q 可随时退出）...")

    ai_client = anthropic.Anthropic(api_key=api_key)

    moved   = 0
    skipped = 0

    try:
        for img in images:
            try:
                ok = process_image(ai_client, img, known_clients)
                if ok:
                    moved += 1
                else:
                    skipped += 1
            except SystemExit:
                break
            except Exception as e:
                print(f"  ❌ 处理出错：{e}")
                skipped += 1
    except KeyboardInterrupt:
        print("\n\n用户中断。")

    print(f"\n{'='*55}")
    print(f" 完成：已归档 {moved} 张，跳过 {skipped} 张")
    print(f"{'='*55}")
    input("\n按 Enter 退出...")


if __name__ == "__main__":
    main()
