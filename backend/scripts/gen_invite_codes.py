"""批量生成激活码脚本。

用法：
    cd backend
    python -m scripts.gen_invite_codes --count 10
    python -m scripts.gen_invite_codes --count 5 --prefix "VIP-" --length 12
"""
import asyncio
import argparse
import random
import string
import sys
import os

# 确保可以 import app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from beanie import init_beanie
from app.config import settings
from app.models.invite_code import InviteCode


def _random_code(prefix: str, length: int) -> str:
    chars = string.ascii_uppercase + string.digits
    return prefix + "".join(random.choices(chars, k=length))


async def main(count: int, prefix: str, length: int):
    await init_beanie(connection_string=settings.mongodb_url, document_models=[InviteCode])

    generated = []
    attempts = 0
    max_attempts = count * 10

    while len(generated) < count and attempts < max_attempts:
        attempts += 1
        code = _random_code(prefix, length)
        exists = await InviteCode.find_one(InviteCode.code == code)
        if exists:
            continue
        doc = InviteCode(code=code)
        await doc.insert()
        generated.append(code)

    if len(generated) < count:
        print(f"[警告] 仅生成了 {len(generated)}/{count} 个激活码（碰撞过多）", file=sys.stderr)

    for c in generated:
        print(c)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量生成激活码")
    parser.add_argument("--count", type=int, default=10, help="生成数量（默认 10）")
    parser.add_argument("--prefix", type=str, default="", help="激活码前缀（可选）")
    parser.add_argument("--length", type=int, default=8, help="随机部分长度（默认 8）")
    args = parser.parse_args()
    asyncio.run(main(args.count, args.prefix, args.length))
