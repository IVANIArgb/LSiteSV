"""Восстановление backend/routes/pages.py из повреждённой копии."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "backend" / "routes" / "pages.py"
OUT = ROOT / "backend" / "routes" / "pages.py"

# Берём текст из GitHub-кэша или текущего файла
CANDIDATES = [
    Path(r"C:\Users\Пользователь\.cursor\projects\c-Users-Desktop-obsidian-DB-projects-LearningSiteSV\agent-tools\8562c510-b9d9-4436-b236-ee65d9eeb3f5.txt"),
    SRC,
]

text = ""
for p in CANDIDATES:
    if p.exists():
        text = p.read_text(encoding="utf-8")
        break

if not text:
    raise SystemExit("Источник pages.py не найден")

# Исправляем строки, испорченные при конвертации HTML→Markdown
text = text.replace('lower.find(" ")', 'lower.find("</head>")')
text = text.replace('lower.rfind(" ")', 'lower.rfind("</body>")')
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
text = text.replace('@app.get("/categories-data/ ")', '@app.get("/categories-data/<path:filepath>")')

lines = text.splitlines()
fixed: list[str] = []
in_register = False
in_nested_def = False
nested_depth = 0

for line in lines:
    stripped = line.strip()
    if not stripped:
        fixed.append("")
        continue

    # Импорты и функции верхнего уровня до register_routes
    if stripped.startswith(("import ", "from ")):
        fixed.append(stripped)
        continue

    if stripped.startswith("def _page_map") or stripped.startswith("def _split_head_body"):
        in_register = False
        fixed.append(stripped)
        continue

    if stripped.startswith("def register_routes"):
        in_register = True
        nested_depth = 0
        fixed.append(stripped)
        continue

    if not in_register:
        # Тело _page_map / _split_head_body — добавляем 4 пробела если строка без отступа
        if line and not line.startswith(" "):
            fixed.append("    " + stripped)
        else:
            fixed.append(line)
        continue

    # Внутри register_routes
    if stripped.startswith("def _") and "@app" not in stripped:
        in_nested_def = True
        fixed.append("    " + stripped)
        continue

    if stripped.startswith("@app."):
        in_nested_def = False
        fixed.append("    " + stripped)
        continue

    if stripped.startswith("def ") and in_nested_def is False and not stripped.startswith("def _render"):
        # route handler после @app
        fixed.append("    " + stripped)
        in_nested_def = True
        continue

    if stripped.startswith("def _render_static_page"):
        fixed.append("    " + stripped)
        in_nested_def = True
        continue

    # Контент: если уже есть отступ 1+, сохраняем; иначе 8 пробелов для тела register_routes
    if line.startswith("        ") or line.startswith("\t"):
        fixed.append(line)
    elif line.startswith("    "):
        fixed.append(line)
    else:
        fixed.append("        " + stripped)

OUT.write_text("\n".join(fixed) + "\n", encoding="utf-8")
print(f"OK: {OUT} ({len(fixed)} lines)")
