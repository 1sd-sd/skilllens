"""skilllens —— 技能包体检器（offline, deterministic, zero-dependency）。

输入：一个 .skill 文件或技能目录
输出：带证据的体检报告（分数 / 问题清单 / 修复建议）
"""

__version__ = "1.1.1"
__all__ = ["load_package", "run_checks", "score", "render_markdown", "render_html"]
