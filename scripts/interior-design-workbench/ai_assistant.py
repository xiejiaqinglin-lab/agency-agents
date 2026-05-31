"""
本地 AI 助手 - 直接调用 Ollama，支持对话和执行命令
用法：python ai_assistant.py
退出：输入 /bye 或按 Ctrl+C
"""

import subprocess
import sys
import json
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"

SYSTEM_PROMPT = """你是一个智能电脑助手，帮助用户管理文件和操作Windows电脑。

当用户需要执行操作时，你应该：
1. 提供具体的 PowerShell 或 CMD 命令
2. 用代码块格式标注命令，例如：
   ```powershell
   Get-ChildItem D:\\AI_System
   ```
3. 解释命令的作用
4. 等待用户确认后再执行

你擅长：文件整理、文件夹操作、重命名文件、查看磁盘空间、管理程序等。
请用中文回复。"""


def check_ollama():
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as r:
            return True
    except Exception:
        return False


def start_ollama():
    print("正在启动 Ollama...")
    subprocess.Popen(
        ["ollama", "serve"],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    import time
    for i in range(10):
        time.sleep(1)
        if check_ollama():
            print("Ollama 已启动\n")
            return True
    return False


def chat(messages):
    data = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read())
    return result["message"]["content"]


def extract_commands(text):
    """提取回复中的 PowerShell / CMD 命令块"""
    commands = []
    lines = text.split("\n")
    in_block = False
    block_type = ""
    current = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_block:
                in_block = True
                tag = stripped[3:].lower().strip()
                block_type = tag if tag else "cmd"
                current = []
            else:
                if current:
                    commands.append((block_type, "\n".join(current)))
                in_block = False
                current = []
        elif in_block:
            current.append(line)

    return commands


def run_command(cmd_type, command):
    print(f"\n执行命令：")
    print(f"  {command}")
    try:
        if "powershell" in cmd_type:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
        else:
            result = subprocess.run(
                command, shell=True,
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )

        output = result.stdout.strip()
        error = result.stderr.strip()

        if output:
            print(f"\n输出：\n{output}")
        if error:
            print(f"\n错误：\n{error}")
        return output or error or "（命令已执行，无输出）"
    except Exception as e:
        return f"执行失败：{e}"


def main():
    print("=" * 50)
    print("  本地 AI 助手（Ollama + qwen2.5:7b）")
    print("  输入 /bye 退出 | 输入 /clear 清除记录")
    print("=" * 50)
    print()

    if not check_ollama():
        if not start_ollama():
            print("❌ 无法启动 Ollama，请手动运行 'ollama serve' 后重试")
            input("\n按 Enter 退出...")
            return

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/bye", "/exit", "/quit"):
            print("再见！")
            break
        if user_input.lower() == "/clear":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("（对话记录已清除）\n")
            continue

        messages.append({"role": "user", "content": user_input})

        print("\nAI 正在思考...", end="", flush=True)
        try:
            reply = chat(messages)
        except Exception as e:
            print(f"\r❌ 连接失败：{e}\n")
            messages.pop()
            continue

        print(f"\rAI: {reply}\n")
        messages.append({"role": "assistant", "content": reply})

        # 检测并询问是否执行命令
        commands = extract_commands(reply)
        for cmd_type, cmd in commands:
            confirm = input(f"是否执行上面的命令？[Y/n]: ").strip().lower()
            if confirm in ("", "y", "yes"):
                output = run_command(cmd_type, cmd)
                # 把执行结果告诉 AI，继续对话
                messages.append({
                    "role": "user",
                    "content": f"命令已执行，输出结果：\n{output}"
                })
                try:
                    followup = chat(messages)
                    print(f"\nAI: {followup}\n")
                    messages.append({"role": "assistant", "content": followup})
                except Exception:
                    pass
            print()


if __name__ == "__main__":
    main()
