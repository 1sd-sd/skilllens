"""规则层：把"技能包好不好"拆成 20 条可判定的检查。

每条规则都必须满足三个条件，否则不进这张表：
1. 可判定：同一个包跑两次结果一致，不依赖模型、不联网。
2. 可解释：失败时能指出**证据**（哪一行、哪个文件）。
3. 可修复：附一条具体的修改动作，而不是"请优化描述"。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .loader import Package, is_junk

DIMENSIONS = {
    "D1": ("触发力", 25, "别人/AI 能不能一眼知道什么时候该用它"),
    "D2": ("结构", 20, "该有的段落有没有，顺序对不对"),
    "D3": ("可执行", 30, "照着做能不能真的做出来"),
    "D4": ("可维护", 25, "三个月后还能不能改，会不会泄露/带垃圾"),
}

LEVELS = {"error": "必须修", "warn": "建议修", "info": "可选"}


@dataclass
class Issue:
    rule: str
    dimension: str
    level: str
    passed: bool
    weight: int
    title: str
    evidence: str = ""
    fix: str = ""

    def as_dict(self) -> dict:
        return {
            "rule": self.rule,
            "dimension": self.dimension,
            "level": self.level,
            "passed": self.passed,
            "weight": self.weight,
            "title": self.title,
            "evidence": self.evidence,
            "fix": self.fix,
        }


@dataclass
class Rule:
    id: str
    dimension: str
    weight: int
    level: str
    title: str
    fix: str
    fn: callable


def _headings(body: str) -> list[str]:
    return [m.group(1).strip().lower() for m in re.finditer(r"^#{1,6}\s+(.+)$", body, re.MULTILINE)]


def _section_text(body: str, keywords: tuple[str, ...]) -> str:
    """取出标题含 keyword 的那一节正文（到下一个同级或更高级标题为止）。"""
    lines = body.splitlines()
    out, capturing, level = [], False, 0
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            depth, title = len(m.group(1)), m.group(2).lower()
            if capturing and depth <= level:
                capturing = False
            if any(k in title for k in keywords):
                capturing, level = True, depth
                continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def _fences(body: str) -> int:
    return len(re.findall(r"^```", body, re.MULTILINE)) // 2


def _numbered_or_bullets(text: str) -> int:
    return len(re.findall(r"^\s*(?:\d+[.)]|[-*+])\s+\S", text, re.MULTILINE))


def _refs(body: str) -> list[str]:
    """从正文里抽出被引用的本地相对路径（不含 URL / 锚点）。"""
    cands = re.findall(r"(?:`|\(|\s)((?:scripts|references|assets|examples|templates)/[\w./\-]+)", body)
    cands += re.findall(r"\]\(([^)#:]+\.(?:py|md|sh|js|json|ya?ml|txt|html|csv))\)", body)
    seen, out = set(), []
    for c in cands:
        c = c.strip().strip("`")
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


PLACEHOLDER = re.compile(r"(TODO|FIXME|XXX|待补充|待填写|此处省略|占位符|lorem ipsum)", re.IGNORECASE)
SECRET = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"(?:api[_-]?key|token|secret)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}['\"])",
    re.IGNORECASE,
)


# ---------------------------------------------------------------- 检查实现

def _c_frontmatter(pkg: Package):
    fm = pkg.frontmatter
    if pkg.extra.get("fm_error"):
        return False, pkg.extra["fm_error"]
    if not fm.get("name"):
        return False, "frontmatter 里没有 name"
    if not fm.get("description"):
        return False, "frontmatter 里没有 description"
    return True, f"name={fm.get('name')!r}, description {len(str(fm.get('description')))} 字符"


def _c_name(pkg: Package):
    name = str(pkg.frontmatter.get("name", "")).strip()
    if not name:
        return False, "无 name"
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        return False, f"name={name!r} 不是 kebab-case（小写字母/数字/连字符）"
    if len(name) > 64:
        return False, f"name 长度 {len(name)} > 64"
    if pkg.root_prefix and name != pkg.root_prefix.strip("/"):
        return False, f"name={name!r} 与包目录名 {pkg.root_prefix.strip('/')!r} 不一致"
    return True, name


def _c_desc_len(pkg: Package):
    desc = str(pkg.frontmatter.get("description", ""))
    n = len(desc.strip())
    if n < 80:
        return False, f"description 仅 {n} 字符（< 80，模型很难判断何时触发）"
    if n > 1024:
        return False, f"description {n} 字符（> 1024，会被截断）"
    return True, f"{n} 字符"


def _c_desc_trigger(pkg: Package):
    desc = str(pkg.frontmatter.get("description", "")).lower()
    cues = ["use when", "whenever", "use it when", "触发", "当你", "当你需要", "如果用户", "ask for", "say "]
    hits = [c for c in cues if c in desc]
    quotes = len(re.findall(r"[\"'“「]", desc))
    if hits and quotes >= 4:
        return True, f"含触发线索 {hits[:2]} + 引号示例"
    if hits:
        return True, f"含触发线索 {hits[:2]}（建议再加 1-2 个用户原话示例）"
    return False, "description 只描述功能，没有'什么时候用'的触发语"


def _c_section_what(pkg: Package):
    hs = _headings(pkg.body)
    if any(k in h for h in hs for k in ("what", "purpose", "做什么", "作用", "功能")):
        return True, "有 What/Purpose 段"
    return False, "缺少 What/Purpose（一句话说清做什么）"


def _c_section_when(pkg: Package):
    hs = _headings(pkg.body)
    if any(k in h for h in hs for k in ("when", "何时", "什么时候", "适用")):
        return True, "有 When 段"
    return False, "缺少 When to use（触发条件）"


def _c_section_io(pkg: Package):
    hs = " ".join(_headings(pkg.body))
    has_in = any(k in hs for k in ("input", "输入"))
    has_out = any(k in hs for k in ("output", "输出", "产出"))
    if has_in and has_out:
        return True, "Input/Output 段齐全"
    missing = [n for n, ok in (("Input", has_in), ("Output", has_out)) if not ok]
    return False, "缺少 " + "/".join(missing) + " 段"


def _c_steps(pkg: Package):
    text = _section_text(pkg.body, ("step", "步骤", "流程", "怎么"))
    if not text:
        return False, "没有 Steps 段"
    n = _numbered_or_bullets(text)
    if n < 3:
        return False, f"Steps 只有 {n} 条（< 3，说明不够具体）"
    return True, f"{n} 条步骤"


def _c_tools(pkg: Package):
    text = _section_text(pkg.body, ("tool", "工具", "依赖", "依赖项"))
    if text:
        return True, "有 Tools/依赖段"
    if re.search(r"\b(python|node|bash|curl|api|脚本|命令行)\b", pkg.body, re.IGNORECASE):
        return True, "正文提到工具/运行时（可显式补一个 Tools 段）"
    return False, "没有说明需要什么工具/运行时"


def _c_code(pkg: Package):
    n = _fences(pkg.body)
    if n:
        return True, f"{n} 个代码块"
    if pkg.exists("scripts"):
        return True, "有 scripts/ 目录"
    return False, "既没有代码块也没有 scripts/，执行细节全靠脑补"


def _c_ref_integrity(pkg: Package):
    refs = _refs(pkg.body)
    if not refs:
        return None, "正文没有引用本地文件"
    missing = [r for r in refs if not any(f.path.startswith(r.rstrip("/")) for f in pkg.files)]
    if missing:
        return False, "引用了但包里不存在：" + ", ".join(missing[:4])
    return True, f"{len(refs)} 处引用全部存在"


def _c_input_contract(pkg: Package):
    text = _section_text(pkg.body, ("input", "输入"))
    if not text:
        return False, "没有 Input 段"
    has_shape = bool(re.search(r"[`|>]|示例|example|格式|format|字段|schema", text, re.IGNORECASE))
    if len(text) < 40 or not has_shape:
        return False, f"Input 段过于笼统（{len(text)} 字符，无格式/示例）"
    return True, f"Input 段 {len(text)} 字符，含格式或示例"


def _c_output_contract(pkg: Package):
    text = _section_text(pkg.body, ("output", "输出", "产出"))
    if not text:
        return False, "没有 Output 段"
    has_shape = bool(re.search(r"[`|>]|\.md|\.json|\.csv|格式|format|示例|模板", text, re.IGNORECASE))
    if len(text) < 30 or not has_shape:
        return False, "Output 段没说清产出物的格式"
    return True, "Output 段给出格式/模板"


def _c_failure(pkg: Package):
    if re.search(r"(失败|错误|error|否则|fallback|兜底|边界|abort|exit code|异常)", pkg.body, re.IGNORECASE):
        return True, "提到失败/边界处理"
    return False, "没有失败路径说明（输入不合规时怎么办）"


def _c_size_lines(pkg: Package):
    lines = pkg.skill_md.count("\n") + 1
    if lines > 500:
        return False, f"SKILL.md {lines} 行（> 500，应拆分到 references/）"
    return True, f"{lines} 行"


def _c_size_bytes(pkg: Package):
    size = len(pkg.skill_md.encode("utf-8"))
    if size > 30_000 and not pkg.exists("references"):
        return False, f"SKILL.md {size // 1024}KB 且无 references/（分层加载失效）"
    return True, f"{size // 1024}KB"


def _c_examples(pkg: Package):
    has = pkg.exists("examples") or any("demo" in f.path.lower() for f in pkg.files)
    if has:
        return True, "有 examples/demo"
    return False, "没有 examples/ 或 demo，别人不知道怎么验证它好用"


def _c_placeholder(pkg: Package):
    hits = PLACEHOLDER.findall(pkg.skill_md)
    if hits:
        uniq = sorted({h.upper() for h in hits})
        return False, f"SKILL.md 仍含占位符：{', '.join(uniq)}"
    return True, "无占位符"


def _c_junk(pkg: Package):
    junk = [f.path for f in pkg.files if is_junk(f.path)]
    if junk:
        return False, "夹带垃圾文件：" + ", ".join(junk[:4])
    return True, "无垃圾文件"


def _c_secret(pkg: Package):
    m = SECRET.search(pkg.skill_md)
    if m:
        return False, f"SKILL.md 出现疑似密钥：{m.group(0)[:12]}…"
    for f in pkg.files:
        if f.is_text and f.path.lower().endswith((".py", ".js", ".json", ".yaml", ".yml", ".env", ".txt")):
            pass  # 文本内容未缓存，只查 SKILL.md 与文件名
    risky = [f.path for f in pkg.files if f.path.lower().endswith((".env", ".pem", ".key"))]
    if risky:
        return False, "包内含敏感文件：" + ", ".join(risky[:3])
    return True, "未发现明文密钥"


RULES: list[Rule] = [
    Rule("TRG001", "D1", 8, "error", "frontmatter 可解析且含 name/description", "在 SKILL.md 顶部补 --- name/description --- 两块", _c_frontmatter),
    Rule("TRG002", "D1", 6, "error", "name 为 kebab-case 且与目录名一致", "把 name 改成 a-z0-9- 形式，并重命名顶层目录", _c_name),
    Rule("TRG003", "D1", 6, "warn", "description 长度 80–1024 字符", "把'做什么+什么时候用+输入输出'压进 80–500 字", _c_desc_len),
    Rule("TRG004", "D1", 5, "warn", "description 含触发语与用户原话", "加 '适用于/Use when …' 并抄 2 条用户会说的话", _c_desc_trigger),
    Rule("STR001", "D2", 6, "error", "有 What/Purpose 段", "加 '## 做什么' 一句话说明", _c_section_what),
    Rule("STR002", "D2", 4, "warn", "有 When to use 段", "加 '## 什么时候用' 列 3 个场景", _c_section_when),
    Rule("STR003", "D2", 4, "error", "有 Input 与 Output 段", "分别加 '## 输入' '## 输出'", _c_section_io),
    Rule("STR004", "D2", 3, "warn", "Steps 至少 3 条", "把流程拆成 3–7 条编号步骤", _c_steps),
    Rule("STR005", "D2", 3, "info", "说明所需工具/运行时", "加 '## 工具' 段", _c_tools),
    Rule("EXE001", "D3", 8, "error", "有代码块或 scripts/", "把关键命令写成 ```bash 块", _c_code),
    Rule("EXE002", "D3", 6, "error", "引用的本地文件都存在", "删掉失效引用或补上缺失文件", _c_ref_integrity),
    Rule("EXE003", "D3", 6, "error", "输入契约明确", "给出输入格式/字段/示例", _c_input_contract),
    Rule("EXE004", "D3", 5, "warn", "输出契约明确", "给出产出格式与样例", _c_output_contract),
    Rule("EXE005", "D3", 5, "info", "有失败路径说明", "补一段'输入不合规时怎么办'", _c_failure),
    Rule("MNT001", "D4", 5, "warn", "SKILL.md ≤ 500 行", "把长内容移到 references/", _c_size_lines),
    Rule("MNT002", "D4", 4, "info", "体积分层合理", "超过 30KB 时拆 references/", _c_size_bytes),
    Rule("MNT003", "D4", 4, "warn", "有 examples/demo", "加一个最小可跑示例", _c_examples),
    Rule("MNT004", "D4", 4, "error", "无占位符残留", "删掉 TODO/待补充 并写实", _c_placeholder),
    Rule("MNT005", "D4", 4, "warn", "无垃圾文件", "打包前删除 ~$/tmp/.DS_Store", _c_junk),
    Rule("MNT006", "D4", 4, "error", "无明文密钥", "改用环境变量，并从包中移除 .env/.pem", _c_secret),
]


def run_checks(pkg: Package) -> list[Issue]:
    issues: list[Issue] = []
    if pkg.error and pkg.kind == "missing":
        return [Issue("PKG000", "D1", "error", False, 100, "包无法读取", pkg.error, "检查路径是否正确")]
    for rule in RULES:
        try:
            result = rule.fn(pkg)
        except Exception as exc:  # 规则自己崩了不能拖垮整份报告
            issues.append(Issue(rule.id, rule.dimension, rule.level, False, rule.weight, rule.title, f"规则执行异常：{exc}", rule.fix))
            continue
        if result is None or result[0] is None:  # N/A：不计入分母
            continue
        passed, evidence = result
        issues.append(Issue(rule.id, rule.dimension, rule.level, passed, rule.weight, rule.title, evidence, "" if passed else rule.fix))
    return issues
