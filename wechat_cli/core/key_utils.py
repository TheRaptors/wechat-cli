"""密钥工具 — 路径匹配、元数据剥离"""

import os
import posixpath


def strip_key_metadata(keys):
    return {k: v for k, v in keys.items() if not k.startswith("_")}


def _is_safe_rel_path(path):
    normalized = path.replace("\\", "/")
    return ".." not in posixpath.normpath(normalized).split("/")


def normalize_key_rel_path(rel_path):
    """把 `账号/db_storage/...` 归一成相对 db_storage 的路径。"""
    normalized = rel_path.replace("\\", "/")
    marker = "/db_storage/"
    idx = normalized.find(marker)
    if idx >= 0:
        normalized = normalized[idx + len(marker):]
    elif normalized.startswith("db_storage/"):
        normalized = normalized[len("db_storage/"):]
    return normalized.replace("/", os.sep)


def normalize_all_keys(keys):
    """归一化 all_keys.json 的相对路径键名。"""
    out = {}
    for rel, info in strip_key_metadata(keys).items():
        out[normalize_key_rel_path(rel)] = info
    return out


def key_path_variants(rel_path):
    normalized = rel_path.replace("\\", "/")
    variants = []
    for candidate in (
        rel_path,
        normalized,
        normalized.replace("/", "\\"),
        normalized.replace("/", os.sep),
        normalize_key_rel_path(rel_path),
    ):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


def get_key_info(keys, rel_path):
    if not _is_safe_rel_path(rel_path):
        return None
    for candidate in key_path_variants(rel_path):
        if candidate in keys and not candidate.startswith("_"):
            return keys[candidate]

    needle = normalize_key_rel_path(rel_path).replace("\\", "/").lower()
    for key, info in keys.items():
        if key.startswith("_"):
            continue
        kn = key.replace("\\", "/").lower()
        if kn == needle or kn.endswith("/" + needle):
            return info
    return None
