# -*- coding: utf-8 -*-
"""Генерация PDF-документа для индивидуального проекта (аттестация, 9 класс)."""

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "attestation-project-plan.pdf"
FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")


class AttestationPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("Arial", "", str(FONT_REGULAR))
        self.add_font("Arial", "B", str(FONT_BOLD))
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Arial", "B", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "LearningSiteSV — план индивидуального проекта", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Страница {self.page_no()}", align="C")

    def title_page(self):
        self.add_page()
        self.ln(40)
        self.set_font("Arial", "B", 18)
        self.set_text_color(30, 60, 120)
        self.multi_cell(self.epw, 10, "Разработка веб-платформы для\nдистанционного обучения\nс системой тестирования знаний", align="C")
        self.ln(8)
        self.set_font("Arial", "", 14)
        self.set_text_color(60, 60, 60)
        self.cell(0, 10, "LearningSiteSV — учебный портал с курсами и тестами", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(20)
        self.set_font("Arial", "", 12)
        self.set_text_color(0, 0, 0)
        lines = [
            "Индивидуальный проект для итоговой аттестации",
            "9 класс",
            "",
            "Тип проекта: практико-ориентированный (информатика)",
            "",
            "2025–2026 учебный год",
        ]
        for line in lines:
            self.cell(0, 8, line, align="C", new_x="LMARGIN", new_y="NEXT")

    def section(self, title: str):
        self.ln(4)
        self.set_x(self.l_margin)
        self.set_font("Arial", "B", 14)
        self.set_text_color(30, 60, 120)
        self.multi_cell(self.epw, 8, title)
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def paragraph(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Arial", "", 11)
        self.multi_cell(self.epw, 6, text)
        self.ln(2)

    def bullet_list(self, items: list[str]):
        self.set_font("Arial", "", 11)
        for item in items:
            self.set_x(self.l_margin)
            self.multi_cell(self.epw, 6, f"  -  {item}")
        self.ln(2)

    def numbered_list(self, items: list[str]):
        self.set_font("Arial", "", 11)
        for i, item in enumerate(items, 1):
            self.set_x(self.l_margin)
            self.multi_cell(self.epw, 6, f"  {i}. {item}")
        self.ln(2)

    def table(self, headers: list[str], rows: list[list[str]], col_widths: list[int] | None = None):
        if col_widths is None:
            width = (self.w - 2 * self.l_margin) / len(headers)
            col_widths = [width] * len(headers)

        self.set_font("Arial", "B", 10)
        self.set_fill_color(230, 240, 250)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 8, header, border=1, fill=True)
        self.ln()

        self.set_font("Arial", "", 10)
        for row in rows:
            x_start = self.get_x()
            y_start = self.get_y()
            max_h = 8
            line_heights = []
            for i, cell in enumerate(row):
                self.set_xy(x_start + sum(col_widths[:i]), y_start)
                self.multi_cell(col_widths[i], 6, cell, border=0)
                line_heights.append(self.get_y() - y_start)
            max_h = max(max(line_heights), 8)
            x = x_start
            for i, cell in enumerate(row):
                self.rect(x, y_start, col_widths[i], max_h)
                x += col_widths[i]
            self.set_xy(x_start, y_start + max_h)
        self.ln(4)


def build_pdf():
    pdf = AttestationPDF()
    pdf.title_page()
    pdf.add_page()

    pdf.section("Актуальность")
    pdf.paragraph(
        "Современный образовательный процесс всё чаще использует цифровые технологии: "
        "электронные материалы, онлайн-тесты, отслеживание прогресса учеников. "
        "Готовые платформы часто сложны, платны или не подходят под задачи конкретной школы."
    )
    pdf.paragraph("Проблема: отсутствует простой инструмент, где можно разместить курсы и уроки, "
                  "добавить тесты к каждому уроку и отслеживать прогресс ученика.")
    pdf.paragraph("Решение: разработка собственной веб-платформы, адаптированной под учебные задачи.")

    pdf.section("Цель проекта")
    pdf.paragraph(
        "Создать и внедрить рабочий прототип веб-платформы для обучения, "
        "которая позволяет просматривать курсы, проходить уроки и сдавать тесты "
        "с автоматической проверкой результатов."
    )

    pdf.section("Задачи проекта")
    pdf.numbered_list([
        "Изучить существующие образовательные платформы и выбрать функции для своего проекта.",
        "Спроектировать структуру сайта: категории - курсы - уроки - тесты.",
        "Разработать серверную часть (API) на Python/Flask для работы с контентом и пользователями.",
        "Создать пользовательский интерфейс: главная страница, список курсов, просмотр уроков.",
        "Реализовать систему тестирования с разными типами вопросов (один ответ, несколько, ввод текста).",
        "Добавить админ-панель для создания и редактирования учебного контента.",
        "Протестировать систему и подготовить демонстрационный курс для защиты.",
    ])

    pdf.section("Гипотеза")
    pdf.paragraph(
        "Если объединить уроки и автоматические тесты в одной веб-платформе, "
        "то процесс самостоятельного обучения станет удобнее, а проверка знаний — "
        "быстрее и объективнее, чем при использовании разрозненных материалов."
    )

    pdf.section("Объект и предмет исследования")
    pdf.table(
        ["", ""],
        [
            ["Объект", "процесс организации дистанционного обучения"],
            ["Предмет", "программные средства для создания учебного портала с тестированием"],
        ],
        col_widths=[35, 155],
    )

    pdf.section("Методы работы")
    pdf.bullet_list([
        "Анализ аналогов (Stepik, Moodle, Google Classroom и др.)",
        "Проектирование (схема страниц, структура данных)",
        "Программирование (Python, HTML, CSS, JavaScript)",
        "Тестирование (проверка работы функций вручную)",
        "Документирование (отчёт, презентация)",
    ])

    pdf.add_page()
    pdf.section("Технологии и инструменты")
    pdf.table(
        ["Компонент", "Технология"],
        [
            ["Backend", "Python, Flask"],
            ["Frontend", "HTML, CSS, JavaScript"],
            ["База данных", "PostgreSQL (пользователи, прогресс, результаты тестов)"],
            ["Контент", "Файловая система (уроки, тексты, тесты)"],
            ["Среда разработки", "VS Code / Cursor"],
            ["Контроль версий", "Git, GitHub"],
        ],
        col_widths=[50, 140],
    )
    pdf.paragraph(
        "Примечание: на защите проекта демонстрируется основной функционал — "
        "курсы, уроки, тесты. Корпоративные функции (Kerberos, Active Directory) "
        "не являются обязательными для школьной аттестации."
    )

    pdf.section("Ожидаемые результаты")
    pdf.numbered_list([
        "Работающий сайт — можно открыть в браузере и пройти демо-курс.",
        "Демо-курс — 1 категория, 1–2 курса, 3–5 уроков с тестами (например, по информатике).",
        "Отчёт — 15–25 страниц с описанием проекта.",
        "Презентация — 10–15 слайдов для защиты (5–7 минут).",
    ])

    pdf.section("План-график работ")
    pdf.table(
        ["Этап", "Срок", "Содержание"],
        [
            ["1. Подготовка", "1 нед.", "Тема, цель, задачи, согласование с учителем"],
            ["2. Анализ", "1 нед.", "Обзор аналогов, выбор функций"],
            ["3. Проектирование", "1 нед.", "Схема сайта, структура демо-курса"],
            ["4. Backend", "2 нед.", "API, база данных, логика тестов"],
            ["5. Frontend", "2 нед.", "Страницы для ученика и администратора"],
            ["6. Контент", "1 нед.", "Демо-курс, вопросы к тестам"],
            ["7. Тестирование", "1 нед.", "Проверка, исправление ошибок"],
            ["8. Оформление", "1–2 нед.", "Отчёт, презентация, репетиция защиты"],
        ],
        col_widths=[42, 22, 126],
    )

    pdf.add_page()
    pdf.section("Структура отчёта")
    pdf.numbered_list([
        "Титульный лист — название, ФИО, класс, школа, учитель, год.",
        "Содержание.",
        "Введение — актуальность, цель, задачи, объект, предмет, методы.",
        "Глава 1. Теоретическая часть: дистанционное обучение; обзор платформ; выбор технологий.",
        "Глава 2. Практическая часть: архитектура; структура контента; реализация функций; система тестирования.",
        "Глава 3. Тестирование и результаты: сценарии проверки; демонстрационный курс.",
        "Заключение — что сделано, что получилось, перспективы развития.",
        "Список литературы и источников.",
        "Приложения — скриншоты, фрагменты кода, ссылка на GitHub.",
    ])

    pdf.section("План презентации (5–7 минут)")
    pdf.numbered_list([
        "Название, автор, класс.",
        "Актуальность — зачем нужен проект.",
        "Цель и задачи.",
        "Как устроен сайт (схема).",
        "Скриншоты: главная, курс, урок, тест, результат.",
        "Использованные технологии.",
        "Итоги и выводы.",
        "«Спасибо за внимание!» — вопросы.",
    ])
    pdf.paragraph(
        "На защите рекомендуется продемонстрировать работу сайта в браузере: "
        "пройти урок и сдать тест в реальном времени."
    )

    pdf.section("Критерии успеха")
    pdf.bullet_list([
        "Сайт запускается локально без ошибок.",
        "Есть минимум один готовый курс с тестами.",
        "Тест проверяется автоматически и показывает результат.",
        "Отчёт и презентация оформлены и готовы к защите.",
        "Автор проекта может объяснить принцип работы системы своими словами.",
    ])

    pdf.section("Рекомендации")
    pdf.bullet_list([
        "На защите показывать основной функционал: вход → курс → урок → тест.",
        "Подготовить демо-курс по информатике — учителю будет проще оценить работу.",
        "Сохранять скриншоты по ходу разработки для отчёта.",
        "Согласовать тему и шаблон отчёта с руководителем проекта заранее.",
    ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    path = build_pdf()
    print(f"PDF создан: {path}")
