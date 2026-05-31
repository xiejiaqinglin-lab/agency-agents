"""
本地 AI 助手 - 支持 DeepSeek / Claude / OpenAI / 本地 Ollama
用法：python ai_assistant.py
退出：输入 /bye 或按 Ctrl+C
"""

import subprocess
import sys
import json
import os
import urllib.request
import urllib.error

# ── 配置区（按需修改）─────────────────────────────────────────
# 选择 AI 提供商：deepseek / claude / openai / ollama
PROVIDER = os.environ.get("AI_PROVIDER", "deepseek")

# API Key（从环境变量读取，或直接填在这里）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CLAUDE_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY   = os.environ.get("OPENAI_API_KEY", "")

# 各提供商配置
PROVIDERS = {
    "deepseek": {
        "url":   "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "key":   lambda: DEEPSEEK_API_KEY,
        "name":  "DeepSeek",
    },
    "openai": {
        "url":   "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "key":   lambda: OPENAI_API_KEY,
        "name":  "OpenAI GPT-4o Mini",
    },
    "claude": {
        "url":   "https://api.anthropic.com/v1/messages",
        "model": "claude-haiku-4-5-20251001",
        "key":   lambda: CLAUDE_API_KEY,
        "name":  "Claude (Anthropic)",
    },
    "ollama": {
        "url":   "http://localhost:11434/api/chat",
        "model": "qwen2.5:7b",
        "key":   lambda: "",
        "name":  "本地 Ollama (qwen2.5:7b)",
    },
}
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个智能Windows电脑助手，帮助用户管理文件和操作电脑。

当用户需要执行操作时：
1. 提供具体的 PowerShell 命令
2. 用代码块格式标注：
   ```powershell
   命令内容
   ```
3. 简单解释命令作用

你擅长：文件整理、重命名、查看空间、管理程序、文件夹操作。
请用中文回复，回答简洁实用。"""


def chat_online(messages, provider_cfg, api_key):
    """调用 DeepSeek / OpenAI 兼容接口"""
    data = json.dumps({
        "model":    provider_cfg["model"],
        "messages": messages,
    }).encode("utf-8")

    req = urllib.request.Request(
        provider_cfg["url"],
        data=data,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.loads(r.read())
    return result["choices"][0]["message"]["content"]


def chat_claude(messages, api_key):
    """调用 Anthropic Claude 接口"""
    system_msg = next((m["content"] for m in messages if m["role"] == "system"), SYSTEM_PROMPT)
    user_messages = [m for m in messages if m["role"] != "system"]

    data = json.dumps({
        "model":      PROVIDERS["claude"]["model"],
        "max_tokens": 1024,
        "system":     system_msg,
        "messages":   user_messages,
    }).encode("utf-8")

    req = urllib.request.Request(
        PROVIDERS["claude"]["url"],
        data=data,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.loads(r.read())
    return result["content"][0]["text"]


def chat_ollama(messages):
    """调用本地 Ollama 接口"""
    data = json.dumps({
        "model":    PROVIDERS["ollama"]["model"],
        "messages": messages,
        "stream":   False,
    }).encode("utf-8")

    req = urllib.request.Request(
        PROVIDERS["ollama"]["url"],
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read())
    return result["message"]["content"]


def check_ollama():
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
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
    for _ in range(10):
        time.sleep(1)
        if check_ollama():
            return True
    return False


def do_chat(messages, provider, api_key):
    if provider == "claude":
        return chat_claude(messages, api_key)
    elif provider == "ollama":
        return chat_ollama(messages)
    else:
        return chat_online(messages, PROVIDERS[provider], api_key)


def extract_commands(text):
    commands = []
    lines = text.split("\n")
    in_block = False
    block_type = "cmd"
    current = []
    for line in lines:
        s = line.strip()
        if s.startswith("```"):
            if not in_block:
                in_block = True
                tag = s[3:].lower().strip()
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
    print(f"\n执行中...")
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
        error  = result.stderr.strip()
        if output:
            print(f"输出：\n{output}")
        if error:
            print(f"错误：\n{error}")
        return output or error or "（已执行，无输出）"
    except Exception as e:
        return f"执行失败：{e}"


def select_provider():
    """启动时让用户选择 AI 提供商"""
    print("\n请选择 AI：")
    keys = list(PROVIDERS.keys())
    for i, k in enumerate(keys, 1):
        print(f"  {i}. {PROVIDERS[k]['name']}")
    while True:
        choice = input("输入编号 [默认 1-DeepSeek]: ").strip()
        if not choice:
            return "deepseek"
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            return keys[int(choice) - 1]
        print("请输入有效编号。")


def main():
    print("=" * 50)
    print("  本地 AI 电脑助手")
    print("  输入 /bye 退出 | /clear 清除记录 | /switch 切换AI")
    print("=" * 50)

    provider = select_provider()
    cfg = PROVIDERS[provider]
    api_key = cfg["key"]()

    # 检查 API Key
    if provider != "ollama" and not api_key:
        print(f"\n❌ 未设置 {cfg['name']} 的 API Key")
        if provider == "deepseek":
            print("  1. 访问 https://platform.deepseek.com 注册")
            print("  2. 充值 ¥10（够用很久）")
            print("  3. 创建 API Key，然后：")
            print('  在 PowerShell 运行：$env:DEEPSEEK_API_KEY="你的Key"')
            print("  再重新启动此程序")
        elif provider == "claude":
            print('  在 PowerShell 运行：$env:ANTHROPIC_API_KEY="你的Key"')
        elif provider == "openai":
            print('  在 PowerShell 运行：$env:OPENAI_API_KEY="你的Key"')
        api_key = input("\n或直接粘贴 API Key（回车跳过）: ").strip()
        if not api_key:
            input("按 Enter 退出...")
            return

    # Ollama 需要先启动
    if provider == "ollama":
        if not check_ollama():
            if not start_ollama():
                print("❌ 无法启动 Ollama")
                input("按 Enter 退出...")
                return

    print(f"\n✓ 已连接：{cfg['name']}")
    print("─" * 50)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("\n你: ").strip()
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
            print("（对话记录已清除）")
            continue
        if user_input.lower() == "/switch":
            provider = select_provider()
            cfg = PROVIDERS[provider]
            api_key = cfg["key"]()
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print(f"已切换到：{cfg['name']}")
            continue

        messages.append({"role": "user", "content": user_input})
        print("\nAI 思考中...", end="", flush=True)

        try:
            reply = do_chat(messages, provider, api_key)
        except Exception as e:
            print(f"\r❌ 请求失败：{e}\n")
            messages.pop()
            continue

        print(f"\rAI: {reply}\n")
        messages.append({"role": "assistant", "content": reply})

        commands = extract_commands(reply)
        for cmd_type, cmd in commands:
            confirm = input("是否执行上面的命令？[Y/n]: ").strip().lower()
            if confirm in ("", "y", "yes"):
                output = run_command(cmd_type, cmd)
                messages.append({"role": "user", "content": f"命令输出：\n{output}"})
                try:
                    followup = do_chat(messages, provider, api_key)
                    print(f"\nAI: {followup}\n")
                    messages.append({"role": "assistant", "content": followup})
                except Exception:
                    pass


if __name__ == "__main__":
    main()
