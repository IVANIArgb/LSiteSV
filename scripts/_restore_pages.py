"""Временный скрипт восстановления backend/routes/pages.py."""
from pathlib import Path

src = Path(__file__).resolve().parent.parent / "backend" / "routes" / "_routes_source.txt"
if not src.exists():
    alt = Path(
        r"C:\Users\Пользователь\.cursor\projects\c-Users-Desktop-obsidian-DB-projects-LearningSiteSV"
        r"\agent-tools\dcd07a3d-4877-4a31-88a1-39d899c2809c.txt"
    )
    if alt.exists():
        src = alt

text = src.read_text(encoding="utf-8")
text = text.replace(
    r'<header[^>]*class=\"[^\"]*header[^\"]*\"[\s\S]*? \s*"',
    r'<header[^>]*class=\"[^\"]*header[^\"]*\"[\s\S]*?</header>\s*"',
)
text = text.replace(
    r'<div[^>]*class=\"[^\"]*made-by[^\"]*\"[\s\S]*? \s*"',
    r'<div[^>]*class=\"[^\"]*made-by[^\"]*\"[\s\S]*?</div>\s*"',
)
text = text.replace(r"<footer[\s\S]*? ", r"<footer[\s\S]*?</footer>")
text = text.replace('@app.get("/uploads/ ")', '@app.get("/uploads/<filename>")')
text = text.replace(
    '@app.get("/categories-data/ ")',
    '@app.get("/categories-data/<path:filepath>")',
)

lines = text.splitlines()
fixed_lines: list[str] = []
in_register = False
for line in lines:
    stripped = line.lstrip()
    if stripped.startswith("def register_routes"):
        in_register = True
        fixed_lines.append(stripped)
        continue
    if in_register and stripped.startswith("def ") and not stripped.startswith("def _"):
        in_register = False
    if stripped.startswith(("import ", "from ")):
        fixed_lines.append(stripped)
    elif stripped.startswith(("def _page_map", "def _split_head_body")):
        fixed_lines.append(stripped)
    elif in_register:
        fixed_lines.append(("    " + stripped) if stripped else "")
    else:
        fixed_lines.append(stripped)

out = Path(__file__).resolve().parent.parent / "backend" / "routes" / "pages.py"
out.write_text("\n".join(fixed_lines) + "\n", encoding="utf-8")
print(f"OK: {out} ({len(fixed_lines)} lines)")
