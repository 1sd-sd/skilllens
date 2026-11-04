"""包加载层：把 .skill(zip) / 目录 / 单个 SKILL.md 统一成 Package 对象。

设计要点
--------
1. 不假设压缩包只有一层目录：先探测公共前缀，再决定 root_prefix。
2. 不修改输入：zip 只在内存里读，目录只读。
3. 出错不抛异常给调用方，而是记录在 Package.error 里——体检器本身不能因为
   被体检的东西坏了就崩掉。
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# 单个文件超过这个大小就不再读全文（只记尺寸）
MAX_READ_BYTES = 2 * 1024 * 1024

JUNK_NAMES = {"thumbs.db", ".ds_store", "desktop.ini"}
JUNK_PREFIXES = ("~$", "._", ".~")
JUNK_SUFFIXES = (".tmp", ".bak", ".swp")


@dataclass
class FileEntry:
    path: str  # 相对 root 的路径，统一用 /
    size: int
    is_text: bool = False

    @property
    def suffix(self) -> str:
        return os.path.splitext(self.path)[1].lower()


@dataclass
class Package:
    source: str
    kind: str  # zip | dir | file
    root_prefix: str = ""
    files: list[FileEntry] = field(default_factory=list)
    skill_md: str = ""
    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    error: str = ""
    extra: dict = field(default_factory=dict)

    def find(self, name: str) -> FileEntry | None:
        name = name.lower()
        for f in self.files:
            if f.path.lower() == name:
                return f
        return None

    def exists(self, rel_prefix: str) -> bool:
        rel_prefix = rel_prefix.lower().rstrip("/") + "/"
        return any(f.path.lower().startswith(rel_prefix) for f in self.files)


_DELIM = re.compile(r"^---\s*$", re.MULTILINE)


def _parse_frontmatter(text: str) -> tuple[dict, str, str]:
    """极简 YAML 子集解析：只支持 key: value / key: > 折行 / 列表项。

    不引入 PyYAML 是刻意的——这个工具要能在任何装了 Python 的机器上跑。
    解析失败时返回空 dict，由规则层报 FRM001。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "缺少 frontmatter 起始 ---"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text, "frontmatter 未闭合（缺少结束 ---）"

    meta: dict = {}
    key = None
    buf: list[str] = []
    scalar_style = ""

    def flush():
        nonlocal key, buf, scalar_style
        if key:
            joined = "\n".join(buf).strip() if scalar_style in (">", "|") else " ".join(p.strip() for p in buf if p.strip())
            meta[key] = joined
        key, buf, scalar_style = None, [], ""

    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(("  ", "\t")) and key:
            buf.append(line)
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if m:
            flush()
            key, raw = m.group(1), m.group(2).strip()
            if raw in (">", "|", ">-", "|-"):
                scalar_style = raw[0]
                buf = []
            elif raw.startswith("[") and raw.endswith("]"):
                meta[key] = [x.strip().strip("'\"") for x in raw[1:-1].split(",") if x.strip()]
                key = None
            else:
                buf = [raw] if raw else []
    flush()

    body = "\n".join(lines[end + 1 :])
    return meta, body, ""


def _from_zip(path: Path) -> Package:
    pkg = Package(source=str(path), kind="zip")
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            if not names:
                pkg.error = "压缩包为空"
                return pkg
            # 探测公共根目录：所有条目都共享的第一段
            roots = {n.split("/")[0] for n in names}
            first_seg_all_dirs = all(len(n.split("/")) > 1 for n in names)
            root = next(iter(roots)) if (len(roots) == 1 and first_seg_all_dirs) else ""
            pkg.root_prefix = (root + "/") if root else ""
            pkg.extra["zip_roots"] = sorted(roots)
            for n in names:
                info = z.getinfo(n)
                rel = n[len(pkg.root_prefix) :] if pkg.root_prefix else n
                pkg.files.append(
                    FileEntry(path=rel, size=info.file_size, is_text=_is_text_name(rel))
                )
            md_name = next((n for n in names if n.lower().endswith("skill.md")), None)
            if md_name is None:
                pkg.error = "包内没有 SKILL.md"
                return pkg
            if md_name.lower() != (pkg.root_prefix + "skill.md").lower():
                pkg.extra["skill_md_nested"] = md_name
            with z.open(md_name) as fh:
                raw = fh.read(MAX_READ_BYTES)
            pkg.skill_md = raw.decode("utf-8", errors="replace")
    except zipfile.BadZipFile:
        pkg.error = "不是合法的 zip（.skill 必须是 zip 格式）"
        return pkg
    except OSError as exc:  # 权限 / 占用
        pkg.error = f"读取失败：{exc}"
        return pkg
    pkg.frontmatter, pkg.body, pkg.extra["fm_error"] = _parse_frontmatter(pkg.skill_md)
    return pkg


def _is_text_name(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in {
        ".md", ".txt", ".py", ".js", ".json", ".yaml", ".yml", ".sh", ".html", ".csv", ".tsv"
    }


def _from_dir(path: Path) -> Package:
    pkg = Package(source=str(path), kind="dir")
    # 目录模式下"包名"就是目录名，与 zip 模式保持一致，name 一致性检查才有意义
    pkg.root_prefix = path.name + "/"
    md = None
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".venv", "node_modules")]
        for fn in files:
            full = Path(root) / fn
            rel = full.relative_to(path).as_posix()
            try:
                size = full.stat().st_size
            except OSError:
                size = 0
            pkg.files.append(FileEntry(path=rel, size=size, is_text=_is_text_name(rel)))
            if fn.lower() == "skill.md" and md is None:
                md = full
    if md is None:
        pkg.error = "目录里没有 SKILL.md"
        return pkg
    try:
        pkg.skill_md = md.read_text(encoding="utf-8", errors="replace")[:MAX_READ_BYTES]
    except OSError as exc:
        pkg.error = f"读取 SKILL.md 失败：{exc}"
        return pkg
    pkg.frontmatter, pkg.body, pkg.extra["fm_error"] = _parse_frontmatter(pkg.skill_md)
    return pkg


def _from_md(path: Path) -> Package:
    pkg = Package(source=str(path), kind="file")
    try:
        pkg.skill_md = path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_BYTES]
    except OSError as exc:
        pkg.error = f"读取失败：{exc}"
        return pkg
    pkg.files = [FileEntry(path=path.name, size=len(pkg.skill_md), is_text=True)]
    pkg.frontmatter, pkg.body, pkg.extra["fm_error"] = _parse_frontmatter(pkg.skill_md)
    return pkg


def load_package(target: str | Path) -> Package:
    path = Path(target)
    if not path.exists():
        return Package(source=str(target), kind="missing", error=f"路径不存在：{target}")
    if path.is_dir():
        return _from_dir(path)
    if zipfile.is_zipfile(path):
        return _from_zip(path)
    if path.suffix.lower() in (".md", ".markdown"):
        return _from_md(path)
    return Package(source=str(target), kind="unknown", error="不支持的类型（需要 .skill / 目录 / .md）")


def is_junk(name: str) -> bool:
    low = name.lower()
    base = low.rsplit("/", 1)[-1]
    return (
        base in JUNK_NAMES
        or base.startswith(JUNK_PREFIXES)
        or base.endswith(JUNK_SUFFIXES)
    )
