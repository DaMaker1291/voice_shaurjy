"""
Diff Renderer — HTML side-by-side and unified diff viewer.
"""

import difflib
import logging
from typing import List, Optional

log = logging.getLogger("jarvis-diff")


def render_side_by_side(old_code: str, new_code: str, old_label: str = "Before",
                        new_label: str = "After", filename: str = "") -> str:
    """Render a side-by-side HTML diff viewer."""
    old_lines = old_code.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=old_label, tofile=new_label, lineterm=""))

    left_lines = []
    right_lines = []
    left_num = 0
    right_num = 0

    for line in diff:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            m = __import__("re").search(r"@@ -(\d+),?\d* \+(\d+),?\d* @@", line)
            if m:
                left_num = int(m.group(1)) - 1
                right_num = int(m.group(2)) - 1
            continue
        if line.startswith("-"):
            left_num += 1
            left_lines.append(f'<div class="diff-line del"><span class="ln">{left_num}</span>{_esc(line[1:])}</div>')
            right_lines.append(f'<div class="diff-line empty"><span class="ln"></span></div>')
        elif line.startswith("+"):
            right_num += 1
            left_lines.append(f'<div class="diff-line empty"><span class="ln"></span></div>')
            right_lines.append(f'<div class="diff-line add"><span class="ln">{right_num}</span>{_esc(line[1:])}</div>')
        else:
            left_num += 1
            right_num += 1
            content = line[1:] if line.startswith(" ") else line
            left_lines.append(f'<div class="diff-line ctx"><span class="ln">{left_num}</span>{_esc(content)}</div>')
            right_lines.append(f'<div class="diff-line ctx"><span class="ln">{right_num}</span>{_esc(content)}</div>')

    title = f"Code Diff{f' — {filename}' if filename else ''}"

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{title}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Cascadia Code','Fira Code',monospace; background:#0a0e1a; color:#e2e8f0; }}
.header {{ background:#1e293b; padding:14px 20px; border-bottom:1px solid #334155; }}
.header h1 {{ font-size:1em; font-weight:600; }}
.container {{ display:flex; height:calc(100vh - 50px); }}
.panel {{ flex:1; overflow-y:auto; border-right:1px solid #1e293b; }}
.panel:last-child {{ border:none; }}
.panel-header {{ background:#1e293b; padding:8px 16px; font-size:0.8em; color:#94a3b8; border-bottom:1px solid #334155; position:sticky; top:0; }}
.diff-line {{ display:flex; padding:1px 0; font-size:0.82em; line-height:1.5; }}
.diff-line .ln {{ width:40px; text-align:right; padding-right:10px; color:#475569; user-select:none; flex-shrink:0; }}
.diff-line .code {{ white-space:pre; }}
.del {{ background:#3b1111; }}
.del .code {{ color:#fca5a5; }}
.add {{ background:#0d2818; }}
.add .code {{ color:#86efac; }}
.ctx {{ background:transparent; }}
.ctx .code {{ color:#94a3b8; }}
.empty {{ background:#0a0e1a; }}
.stats {{ display:flex; gap:16px; padding:8px 16px; background:#111827; font-size:0.8em; }}
.stat-add {{ color:#4ade80; }}
.stat-del {{ color:#f87171; }}
</style></head><body>
<div class="header"><h1>{title}</h1></div>
<div class="stats">
<span class="stat-add">+{sum(1 for l in left_lines if 'add' in l)} additions</span>
<span class="stat-del">-{sum(1 for l in left_lines if 'del' in l)} deletions</span>
</div>
<div class="container">
<div class="panel"><div class="panel-header">{old_label}</div>{"".join(left_lines)}</div>
<div class="panel"><div class="panel-header">{new_label}</div>{"".join(right_lines)}</div>
</div></body></html>"""


def render_unified(old_code: str, new_code: str, filename: str = "") -> str:
    """Render a unified HTML diff."""
    old_lines = old_code.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{filename}", tofile=f"b/{filename}", lineterm=""))

    lines_html = []
    for line in diff:
        if line.startswith("+"):
            lines_html.append(f'<div class="add">{_esc(line)}</div>')
        elif line.startswith("-"):
            lines_html.append(f'<div class="del">{_esc(line)}</div>')
        elif line.startswith("@@"):
            lines_html.append(f'<div class="hunk">{_esc(line)}</div>')
        else:
            lines_html.append(f'<div class="ctx">{_esc(line)}</div>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Diff: {filename}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Cascadia Code','Fira Code',monospace; background:#0a0e1a; color:#e2e8f0; padding:16px; font-size:0.85em; }}
.add {{ background:#0d2818; color:#86efac; padding:2px 8px; }}
.del {{ background:#3b1111; color:#fca5a5; padding:2px 8px; }}
.ctx {{ color:#94a3b8; padding:2px 8px; }}
.hunk {{ color:#60a5fa; padding:4px 8px; background:#1e293b; margin:8px 0; }}
</style></head><body>{"".join(lines_html)}</body></html>"""


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
