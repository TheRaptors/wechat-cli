#!/usr/bin/env python3
"""用 ~/.wechat-cli/all_keys.json 解密微信 SQLCipher 数据库。

依赖本仓库已安装的 wechat-cli（pip install -e .），以及事先完成的
`wechat-cli init`。

用法见文件末尾，或:

    python scripts/decrypt_db.py --help
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

from wechat_cli.core.config import load_config
from wechat_cli.core.crypto import decrypt_wal, full_decrypt
from wechat_cli.core.key_utils import get_key_info, normalize_all_keys, key_path_variants


def _list_keys(keys: dict) -> None:
    print(f"共 {len(keys)} 个可解密数据库:\n")
    for rel in sorted(keys, key=lambda s: s.replace("\\", "/").lower()):
        info = keys[rel]
        size = info.get("size_mb")
        size_s = f"{size}MB" if size is not None else "?"
        print(f"  {rel.replace(chr(92), '/'):<45} {size_s}")


def _resolve_rel(keys: dict, name: str) -> str | None:
    """把用户输入解析成 all_keys 里的相对路径。"""
    name = name.strip().replace("/", os.sep).replace("\\", os.sep)
    # 直接命中
    if get_key_info(keys, name):
        for v in key_path_variants(name):
            if v in keys:
                return v
        # suffix 命中：返回 keys 里真实键名
        needle = name.replace("\\", "/").lower()
        for k in keys:
            kn = k.replace("\\", "/").lower()
            if kn == needle or kn.endswith("/" + needle) or kn.endswith("/" + os.path.basename(needle)):
                if os.path.basename(kn) == os.path.basename(needle) or kn.endswith("/" + needle):
                    return k

    # 只给了文件名，如 message_0.db / favorite.db
    base = os.path.basename(name).lower()
    matches = [k for k in keys if os.path.basename(k).lower() == base]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print("[!] 多个库同名，请写相对路径之一:", file=sys.stderr)
        for m in matches:
            print(f"    {m.replace(chr(92), '/')}", file=sys.stderr)
        return None
    return None


def _default_out_name(rel: str) -> str:
    base = os.path.splitext(os.path.basename(rel))[0]
    today = date.today().strftime("%Y.%m.%d")
    return f"{base}_{today}.db"


def decrypt_one(db_dir: str, keys: dict, rel: str, out_path: str, apply_wal: bool) -> None:
    info = get_key_info(keys, rel)
    if not info:
        raise SystemExit(f"密钥中找不到: {rel}")

    src = os.path.join(db_dir, rel.replace("/", os.sep))
    if not os.path.isfile(src):
        raise SystemExit(f"源文件不存在: {src}")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    enc_key = bytes.fromhex(info["enc_key"])
    pages = full_decrypt(src, out_path, enc_key)
    wal_frames = 0
    wal = src + "-wal"
    if apply_wal and os.path.exists(wal):
        wal_frames = decrypt_wal(wal, out_path, enc_key)

    size = os.path.getsize(out_path)
    print(f"[+] {rel.replace(chr(92), '/')} -> {out_path}")
    print(f"    size={size} bytes, pages={pages}, wal_frames={wal_frames}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="解密微信本地 SQLCipher 数据库（需先 wechat-cli init）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出可解密的库
  python scripts/decrypt_db.py --list

  # 按文件名解密到当前目录（默认带日期后缀）
  python scripts/decrypt_db.py message_0.db
  python scripts/decrypt_db.py favorite.db

  # 指定相对路径与输出文件名
  python scripts/decrypt_db.py message/message_0.db -o message_0_2026.09.28.db
  python scripts/decrypt_db.py favorite/favorite.db -o favorite_plain.db

  # 一次解密多个
  python scripts/decrypt_db.py message_0.db session/session.db contact/contact.db
""",
    )
    parser.add_argument(
        "databases",
        nargs="*",
        help="要解密的库：文件名或相对 db_storage 的路径，如 message_0.db / message/message_0.db",
    )
    parser.add_argument("-o", "--output", help="输出路径（仅当只解密一个库时可用）")
    parser.add_argument("-l", "--list", action="store_true", help="列出 all_keys.json 中的数据库")
    parser.add_argument("--no-wal", action="store_true", help="不合并 -wal 增量页")
    parser.add_argument(
        "--config",
        default=None,
        help="config.json 路径（默认 ~/.wechat-cli/config.json）",
    )
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
    except FileNotFoundError as e:
        raise SystemExit(f"{e}\n请先运行: wechat-cli init") from e

    keys_file = cfg["keys_file"]
    if not os.path.isfile(keys_file):
        raise SystemExit(f"密钥文件不存在: {keys_file}\n请先运行: wechat-cli init")

    with open(keys_file, encoding="utf-8") as f:
        keys = normalize_all_keys(json.load(f))

    if args.list or not args.databases:
        if not args.databases and not args.list:
            parser.print_help()
            print()
        _list_keys(keys)
        if not args.databases:
            return

    if args.output and len(args.databases) != 1:
        raise SystemExit("-o/--output 只能在解密单个数据库时使用")

    db_dir = cfg["db_dir"]
    apply_wal = not args.no_wal

    for name in args.databases:
        rel = _resolve_rel(keys, name)
        if not rel:
            raise SystemExit(f"无法匹配数据库: {name}（用 --list 查看可用列表）")
        out = args.output if args.output else _default_out_name(rel)
        decrypt_one(db_dir, keys, rel, out, apply_wal)


if __name__ == "__main__":
    main()
