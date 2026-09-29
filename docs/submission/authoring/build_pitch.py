"""Build the editable TalkNFace organizer pitch (16:9 PPTX)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from lxml import etree

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "docs" / "submission" / "assets"
EVIDENCE = ROOT / "docs" / "gates" / "evidence"
PPTX = ROOT / "docs" / "submission" / "TALKNFACE_PRODUCT_PITCH_RU.pptx"

TEAL = "17695e"
TEAL_DARK = "104f47"
TEAL_SOFT = "e3efea"
INK = "183331"
BODY = "203240"
MUTED = "586b72"
LINE = "dce5e2"
WHITE = "ffffff"
BG = "f3f6f5"
ORANGE = "bc6b1b"
CREAM = "fff6ea"
DANGER_BG = "fff1ed"
DANGER = "792b24"


def rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def crop(src: Path, box: tuple[int, int, int, int], dest: Path) -> None:
    im = Image.open(src).convert("RGB")
    cut = im.crop(box)
    # Thin product-like frame so crops sit cleanly on the slide.
    framed = Image.new("RGB", (cut.width + 2, cut.height + 2), (220, 229, 226))
    framed.paste(cut, (1, 1))
    dest.parent.mkdir(parents=True, exist_ok=True)
    framed.save(dest, "PNG", optimize=True)


def prepare_assets() -> dict[str, Path]:
    ASSETS.mkdir(parents=True, exist_ok=True)
    files = {
        "hero": (EVIDENCE / "app-qwen-independent-01" / "app-s2-result-1280.png", (150, 78, 1130, 1000)),
        "dialogue": (EVIDENCE / "app-qwen-independent-01" / "app-s2-result-1280.png", (160, 1680, 1120, 2580)),
        "settings": (EVIDENCE / "app-g5-context-configuration-01" / "g5-initial-1280-viewport.png", (40, 240, 1240, 820)),
        "preview": (EVIDENCE / "app-clean-machine-reproducibility-01" / "clean-preview-S1.png", (40, 40, 1240, 880)),
        "move": (EVIDENCE / "app-clean-machine-reproducibility-01" / "clean-continued-after-restart.png", (8, 8, 382, 720)),
        "evidence": (EVIDENCE / "app-g6-deterministic-feedback-01" / "g6-s1-evidence-390.png", (4, 0, 386, 530)),
        "process100": (EVIDENCE / "app-clean-machine-reproducibility-01" / "clean-feedback-S1.png", (8, 88, 382, 800)),
        "poor": (EVIDENCE / "app-g6-deterministic-feedback-01" / "g6-poor-report-360.png", (4, 4, 356, 640)),
        "insufficient": (EVIDENCE / "app-g6-deterministic-feedback-01" / "g6-insufficient-390.png", (8, 8, 382, 620)),
        "noagree": (EVIDENCE / "app-g6-deterministic-feedback-01" / "g6-no-agreement-360.png", (4, 4, 356, 560)),
        "login": (EVIDENCE / "app-clean-machine-reproducibility-01" / "clean-admin-login.png", (180, 40, 1100, 820)),
        "publish": (EVIDENCE / "app-g8-access-boundary-01" / "g8-published-S2.png", (8, 120, 382, 780)),
    }
    out = {}
    for name, (src, box) in files.items():
        dest = ASSETS / f"{name}.png"
        crop(src, box, dest)
        out[name] = dest
    return out


def set_run(run, text, size, color, bold=False, name="Calibri"):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    run.font.name = name
    rPr = run._r.get_or_add_rPr()
    latin = rPr.find(qn("a:latin"))
    if latin is None:
        latin = etree.SubElement(rPr, qn("a:latin"))
    latin.set("typeface", name)
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", name)
    cs = rPr.find(qn("a:cs"))
    if cs is None:
        cs = etree.SubElement(rPr, qn("a:cs"))
    cs.set("typeface", name)


def add_text(slide, l, t, w, h, text, size=16, color=BODY, bold=False, name="Calibri",
             align="left", anchor="top"):
    box = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    if anchor == "middle":
        tf.paragraphs[0].alignment = PP_ALIGN.LEFT
        box.text_frame._txBody.bodyPr.set("anchor", "ctr")
    p = tf.paragraphs[0]
    p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
    p.space_after = Pt(0)
    p.space_before = Pt(0)
    run = p.add_run()
    set_run(run, text, size, color, bold, name)
    return box


def add_para(tf, text, size=16, color=BODY, bold=False, name="Calibri", space_before=6, align="left"):
    p = tf.add_paragraph()
    p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
    p.space_before = Pt(space_before)
    p.space_after = Pt(0)
    run = p.add_run()
    set_run(run, text, size, color, bold, name)
    return p


def add_rect(slide, l, t, w, h, fill, line=None, rounded=True):
    shape = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(shape, Inches(l), Inches(t), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = rgb(fill)
    if line:
        sh.line.color.rgb = rgb(line)
        sh.line.width = Pt(1)
    else:
        sh.line.fill.background()
    if rounded:
        try:
            sh.adjustments[0] = 0.08
        except Exception:
            pass
    return sh


def add_picture(slide, path, l, t, w, h):
    return slide.shapes.add_picture(str(path), Inches(l), Inches(t), Inches(w), Inches(h))


def add_picture_fit(slide, path, l, t, w, h):
    im = Image.open(path)
    ar = im.width / im.height
    box_ar = w / h
    if ar > box_ar:
        nh = w / ar
        return add_picture(slide, path, l, t + (h - nh) / 2, w, nh)
    nw = h * ar
    return add_picture(slide, path, l + (w - nw) / 2, t, nw, h)


def add_link(slide, l, t, w, h, label, url, size=16):
    box = add_text(slide, l, t, w, h, label, size=size, color=TEAL, bold=True, name="Segoe UI")
    run = box.text_frame.paragraphs[0].runs[0]
    run.hyperlink.address = url
    return box


def add_notes(slide, text):
    notes = slide.notes_slide
    tf = notes.notes_text_frame
    tf.text = text


def new_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(BG)
    add_rect(slide, 0, 0, 13.333, 0.09, TEAL, rounded=False)
    return slide


def footer(slide, n, extra="TalkNFace · Арена переговоров"):
    add_text(slide, 0.45, 7.18, 10.2, 0.24, extra, size=11, color=MUTED, name="Segoe UI")
    add_text(slide, 11.6, 7.18, 1.25, 0.24, str(n), size=11, color=MUTED, name="Segoe UI", align="right")


def eyebrow(slide, text, l=0.45, t=0.22, w=8):
    add_text(slide, l, t, w, 0.28, text.upper(), size=11, color=TEAL, bold=True, name="Segoe UI")


def headline(slide, text, l=0.45, t=0.46, w=12.4, h=1.15, size=28):
    add_text(slide, l, t, w, h, text, size=size, color=INK, bold=True, name="Segoe UI")


def caption(slide, l, t, w, h, text):
    add_text(slide, l, t, w, h, text, size=11, color=MUTED, name="Calibri")


def build():
    assets = prepare_assets()
    prs = Presentation()
    prs.slide_width = Inches(13.333333)
    prs.slide_height = Inches(7.5)

    # --- 1 ---
    s = new_slide(prs)
    eyebrow(s, "TalkNFace  ·  Арена переговоров")
    headline(s, "Отрепетируйте сложный разговор до реальной встречи", w=7.3, h=1.45, size=30)
    add_text(s, 0.45, 2.05, 6.9, 1.15,
             "Закупщик или руководитель проходит учебную встречу, видит, как вопрос, уступка или отказ меняют исход, и пробует другой подход.",
             size=18, color=BODY, name="Calibri")
    chips = [
        (0.45, "Без AI и ключей"),
        (2.75, "Исход от действий"),
        (5.05, "Повтор ситуации"),
    ]
    for x, label in chips:
        add_rect(s, x, 3.35, 2.2, 0.42, TEAL_SOFT, TEAL_SOFT)
        add_text(s, x + 0.06, 3.42, 2.08, 0.3, label, size=12, color=TEAL_DARK, bold=True, name="Segoe UI", align="center")
    add_rect(s, 0.45, 4.05, 6.9, 2.85, WHITE, LINE)
    add_text(s, 0.7, 4.22, 6.4, 0.32, "Что делает человек", size=13, color=TEAL, bold=True, name="Segoe UI")
    steps = [
        "Администратор задаёт сферу, тему, сложность, тон, роль и цель.",
        "Игрок выбирает вопросы, факты, доводы и пакет условий.",
        "Движок считает последствия. Разбор ссылается на сохранённый ход.",
    ]
    y = 4.6
    for i, line in enumerate(steps, 1):
        add_rect(s, 0.7, y, 0.38, 0.38, TEAL, rounded=True)
        add_text(s, 0.7, y + 0.04, 0.38, 0.32, str(i), size=14, color=WHITE, bold=True, name="Segoe UI", align="center")
        add_text(s, 1.22, y, 5.85, 0.5, line, size=15, color=BODY)
        y += 0.68
    add_rect(s, 7.55, 0.95, 5.35, 5.95, WHITE, LINE)
    add_picture_fit(s, assets["hero"], 7.68, 1.08, 5.09, 5.35)
    caption(s, 7.68, 6.48, 5.09, 0.32, "Реальный результат S2. Guided-режим, без внешнего API.")
    footer(s, 1)
    add_notes(s, """0:00–0:35. Откройте с обещания, не со стека.
«TalkNFace — Арена переговоров. Отрепетируйте сложный разговор до реальной встречи.»
Покажите кадр настоящего экрана: цель достигнута, условия сделки, полезность 47 против альтернативы 25. Это учебная модель, не оценка сотрудника.
Сразу скажите честно: демо guided, без живого AI. Ценность уже есть: выбор → последствие → разбор → повтор.
Переход: «Зачем репетировать? Потому что на настоящей встрече нет паузы на учебник.»""")

    # --- 2 ---
    s = new_slide(prs)
    eyebrow(s, "Ситуация, которую узнают")
    headline(s, "Знать приём мало. На встрече ответ выбирают сразу", h=0.95, size=28)
    add_rect(s, 0.45, 1.85, 12.4, 1.35, WHITE, LINE)
    add_text(s, 0.7, 2.0, 11.9, 1.05,
             "Плановая поставка. Закупщик обсуждает цену, график и предоплату с директором продаж. Производство не должно встать, бюджет нельзя отдать целиком. Книжка про интересы сторон не делает этот выбор за человека.",
             size=17, color=BODY)
    cards = [
        ("Лекция и чек-лист", "Дают словарь: интересы, альтернатива, пакет. Не требуют ответить оппоненту в эту минуту."),
        ("Живой тренинг", "Сильный разбор, но дорого собрать пару и повторить ту же сцену несколько раз."),
        ("Пробел, который закрываем", "Безопасные попытки в том же контексте, с видимой ценой конкретного хода."),
    ]
    for i, (title, body) in enumerate(cards):
        x = 0.45 + i * 4.2
        add_rect(s, x, 3.4, 4.0, 3.35, WHITE, LINE)
        add_rect(s, x, 3.4, 4.0, 0.12, TEAL if i != 1 else MUTED, rounded=False)
        add_text(s, x + 0.25, 3.7, 3.5, 0.7, title, size=18, color=INK, bold=True, name="Segoe UI")
        add_text(s, x + 0.25, 4.45, 3.5, 1.9, body, size=15, color=BODY)
    footer(s, 2)
    add_notes(s, """0:35–1:05. Не проценты рынка и не «тренеры бесполезны».
Опишите одну сцену S1: плановая поставка, директор продаж, цена / график / предоплата.
Лекция не бесполезна — она не создаёт давление выбора. Живой тренинг ценен, но его трудно повторить в том же составе.
Наша гипотеза, не измеренный ROI: короткие попытки с последствиями помогают перенести знание в действие.
Переход: «Как выглядит попытка в продукте.»""")

    # --- 3 ---
    s = new_slide(prs)
    eyebrow(s, "Путь пользователя")
    headline(s, "Настроить → договориться → понять → повторить иначе", h=0.7, size=26)
    loop = [
        ("1. Настроить", "Администратор", "Шесть полей. Проверка. Предпросмотр. Явная публикация."),
        ("2. Договариваться", "Игрок", "Цель и альтернатива до хода. Затем вопрос, факт, довод, пакет."),
        ("3. Понять", "Игрок", "Исход сделки отдельно от процесса. Ссылка на сохранённый ход."),
        ("4. Иначе", "Игрок", "Повтор той же версии. Старая попытка не затирается."),
    ]
    for i, (title, who, body) in enumerate(loop):
        x = 0.45 + i * 3.2
        add_rect(s, x, 1.35, 3.05, 2.15, WHITE, LINE)
        add_text(s, x + 0.18, 1.48, 2.7, 0.35, title, size=16, color=TEAL, bold=True, name="Segoe UI")
        add_text(s, x + 0.18, 1.85, 2.7, 0.28, who, size=12, color=MUTED, bold=True)
        add_text(s, x + 0.18, 2.18, 2.7, 1.1, body, size=14, color=BODY)
    add_rect(s, 0.45, 3.65, 12.4, 3.25, WHITE, LINE)
    add_picture_fit(s, assets["settings"], 0.6, 3.75, 12.1, 2.85)
    caption(s, 0.6, 6.62, 12.1, 0.22, "Администратор задаёт шесть полей. Игрок затем выбирает ход из списка, не свободный текст.")
    footer(s, 3)
    add_notes(s, """1:05–1:45. Чётко разделите роли.
Администратор не играет за оппонента: он задаёт контекст, проверяет достижимость, публикует.
Игрок без регистрации выбирает действия из списка. Это не линейный тест: оппонент раскрывает факты по правилам, пакет может быть принят, отвергнут или закончиться отказом.
Подготовка до первого хода обязательна, если хотите зачёт за неё: галочка в брифинге сама балл не ставит.
Переход: «Покажем две попытки в одной закупке.»""")

    # --- 4 ---
    s = new_slide(prs)
    eyebrow(s, "Учебные примеры, не исследование навыка")
    headline(s, "Одна ситуация — два решения и два разных исхода", h=0.7, size=26)
    add_text(s, 0.45, 1.22, 12.4, 0.55,
             "Обе попытки — неизменённый эталон «Закупка к запуску»: обычная сложность, нейтральный тон, директор продаж, оборотные средства. Живой показ использует другую, настроенную версию.",
             size=14, color=MUTED)
    add_rect(s, 0.45, 1.9, 6.1, 4.9, WHITE, LINE)
    add_rect(s, 0.45, 1.9, 6.1, 0.1, TEAL, rounded=False)
    add_text(s, 0.7, 2.15, 5.6, 0.4, "А. Сначала слушает", size=20, color=INK, bold=True, name="Segoe UI")
    add_text(s, 0.7, 2.65, 5.6, 1.55,
             "Вопрос о логистике, признание экономии, довод, вопрос об оплате. Затем пакет: 95 / 40% на день 7, остаток на 14 / предоплата 50%.",
             size=16, color=BODY)
    add_rect(s, 0.7, 4.4, 5.55, 2.05, TEAL_SOFT, TEAL_SOFT)
    add_text(s, 0.9, 4.55, 5.2, 1.75, "Соглашение. Полезность 64 — выше цели 62 и альтернативы 55.\nПроцесс 100 по 7 применимым проверкам.", size=16, color=TEAL_DARK)
    add_rect(s, 6.75, 1.9, 6.1, 4.9, WHITE, LINE)
    add_rect(s, 6.75, 1.9, 6.1, 0.1, ORANGE, rounded=False)
    add_text(s, 7.0, 2.15, 5.6, 0.4, "Б. Предлагает и выходит", size=20, color=INK, bold=True, name="Segoe UI")
    add_text(s, 7.0, 2.65, 5.6, 1.55,
             "Тот же пакет — первым ходом, затем вопросы. Игрок сам выбирает выход без сделки.",
             size=16, color=BODY)
    add_rect(s, 7.0, 4.4, 5.55, 2.05, CREAM, CREAM)
    add_text(s, 7.2, 4.55, 5.2, 1.75, "Соглашения нет. Процесс 70: зачёт за взаимный пакет остаётся.\nЭто выбор выхода, не рост навыка.", size=16, color="72501e")
    footer(s, 4)
    add_notes(s, """1:45–2:25. Обе попытки — неизменённый эталон S1 «Закупка к запуску»: запуск производства, обычная сложность, нейтральный тон, директор, оборотные средства. Источники: s1-supply-launch.ts, feedback.test.ts, e2e feedback.spec.ts. Это не настроенная плановая поставка живого показа.
А: полезность 64, процесс 100.
Б: тот же пакет первым, затем вопросы, затем явный выход без сделки. Соглашения нет, процесс 70. Не говорите, что сам порядок вопросов автоматически дал отказ: финал — потому что игрок вышел.
Не вычитайте 100 и 70 как рост компетенции. Не переводите 64 в рубли.
Живой показ отдельно: плановая поставка, дружелюбный тон, доходность.
Переход: «Тот же продукт — и для разговора о нагрузке.»""")

    # --- 5 ---
    s = new_slide(prs)
    eyebrow(s, "Конфигурируемость")
    headline(s, "Закупка и нагрузка команды: один тренажёр, шесть настроек", h=0.95, size=26)
    add_rect(s, 0.45, 1.55, 6.1, 2.15, WHITE, LINE)
    add_text(s, 0.7, 1.7, 5.6, 0.35, "S1. Промышленные закупки", size=18, color=INK, bold=True, name="Segoe UI")
    add_text(s, 0.7, 2.15, 5.6, 1.3, "Цена, график партии, предоплата. Плановая поставка допускает всю партию на день 14; запуск производства — нет. Проверенный пакет: полезность 64.", size=14, color=BODY)
    add_rect(s, 6.75, 1.55, 6.1, 2.15, WHITE, LINE)
    add_text(s, 7.0, 1.7, 5.6, 0.35, "S2. Срочная задача и нагрузка", size=18, color=INK, bold=True, name="Segoe UI")
    add_text(s, 7.0, 2.15, 5.6, 1.3, "Объём, срок, помощник, перенос отчёта. Проверенный путь: полный объём / 2 дня / помощник / перенос. Полезность 47, цель 45.", size=14, color=BODY)
    effects = [
        ("Сфера", "Меняет предмет и единицы: деньги и график либо часы и ресурсы."),
        ("Тема", "Меняет допустимые условия. Недостижимый запрос не публикуется."),
        ("Сложность", "Когда оппонент раскрывает интерес и насколько жёстко принимает пакет. До 8 ходов."),
        ("Тон", "Стартовое доверие и напряжение. Скептик слабее снимает напряжение признанием факта."),
        ("Роль", "Полномочия: директор согласует цену шире, менеджер — уже; лид может сам предложить помощь."),
        ("Цель", "Что для оппонента ценнее: оборот или доходность; нагрузка или полный объём."),
    ]
    for i, (title, body) in enumerate(effects):
        x = 0.45 + (i % 3) * 4.2
        y = 3.9 + (i // 3) * 1.5
        add_rect(s, x, y, 4.05, 1.38, WHITE, LINE)
        add_text(s, x + 0.18, y + 0.12, 3.7, 0.32, title, size=14, color=TEAL, bold=True, name="Segoe UI")
        add_text(s, x + 0.18, y + 0.46, 3.7, 0.8, body, size=13, color=BODY)
    footer(s, 5)
    add_notes(s, """2:35–3:15. Две семьи, не «любая отрасль».
Шесть полей совпадают с постановкой PDF. Эффекты — из компилятора G5, без раскрытия скрытых порогов цены.
Не обещайте, что каждая комбинация валидна: тема «переприоритизация» в этой версии отклоняется, потому что без помощника цель 45 недостижима.
Третьей семьи сценариев нет.
Переход: «После попытки человек видит не оценку личности, а разбор ходов.»""")

    # --- 6 ---
    s = new_slide(prs)
    eyebrow(s, "Обратная связь")
    headline(s, "Разбор указывает на сохранённый ход, а не на общий совет", h=0.7, size=26)
    add_rect(s, 0.45, 1.4, 5.15, 5.45, WHITE, LINE)
    add_picture_fit(s, assets["evidence"], 0.6, 1.52, 4.85, 5.2)
    add_rect(s, 5.8, 1.4, 7.05, 1.7, WHITE, LINE)
    add_text(s, 6.0, 1.52, 6.65, 0.35, "Сделка и процесс — разные вещи", size=16, color=INK, bold=True, name="Segoe UI")
    add_text(s, 6.0, 1.95, 6.65, 1.0, "Полезность — про пакет. Балл процесса — про записанные действия. 100 из 100 — не компетентность человека.", size=15, color=BODY)
    add_rect(s, 5.8, 3.25, 7.05, 1.55, WHITE, LINE)
    add_text(s, 6.0, 3.37, 6.65, 0.35, "Слабое соглашение", size=16, color=INK, bold=True, name="Segoe UI")
    add_text(s, 6.0, 3.78, 6.65, 0.85, "В нагрузке команды урезанный пакет: полезность 20, процесс 44.12. Подготовка может быть зачтена, аргументация — нет.", size=15, color=BODY)
    add_rect(s, 5.8, 4.95, 7.05, 1.9, WHITE, LINE)
    add_text(s, 6.0, 5.07, 6.65, 0.35, "Один следующий фокус", size=16, color=INK, bold=True, name="Segoe UI")
    add_text(s, 6.0, 5.48, 6.65, 1.2, "Совет привязан к непройденной проверке и не обещает согласия. Мало ходов или нет подготовки — «Недостаточно наблюдений», общего балла нет.", size=15, color=BODY)
    footer(s, 6)
    add_notes(s, """3:15–3:55. На экране — фрагмент настоящего разбора: проверка «взаимный пакет», объяснение и ссылка «Ход 5» на сохранённую фразу.
100 — 7 применимых проверок из 12, не компетенция человека.
44.12 в S2 — веса проверок, не «человек на 44%».
«Недостаточно наблюдений» — если нет явной подготовки или мало событий. Второй скриншот для этого не показываем: он был слишком мелким.
Переход: «Кому это нужно — как гипотеза, не как клиентский кейс.»""")

    # --- 7 ---
    s = new_slide(prs)
    eyebrow(s, "Ценность")
    headline(s, "Повторяемая практика для игрока и понятный контур для организатора", h=1.05, size=25)
    roles = [
        ("Игрок", "Начинающий закупщик или руководитель", "Несколько попыток без стыда за «не тот» ответ. Видит, какой ход изменил исход, и повторяет ту же версию."),
        ("Администратор и наставник", "Готовят занятие, не играют оппонента", "Администратор публикует ситуацию. Отчёт видит сам игрок. Наставник разбирает его вместе с игроком, на экране игрока."),
        ("Возможный покупатель", "HR / L&D, гипотеза", "Короткий корпоративный модуль soft skills. Нет пилотов, договоров и измеренного ROI. Алабуга — автор кейса, не наш клиент."),
    ]
    for i, (title, who, body) in enumerate(roles):
        x = 0.45 + i * 4.2
        add_rect(s, x, 1.7, 4.05, 4.95, WHITE, LINE)
        add_rect(s, x, 1.7, 4.05, 0.12, TEAL, rounded=False)
        add_text(s, x + 0.25, 2.0, 3.55, 0.7, title, size=20, color=INK, bold=True, name="Segoe UI")
        add_text(s, x + 0.25, 2.75, 3.55, 0.7, who, size=14, color=TEAL, bold=True)
        add_text(s, x + 0.25, 3.55, 3.55, 2.7, body, size=15, color=BODY)
    footer(s, 7)
    add_notes(s, """4:00–4:30. Три роли.
Игрок получает свой отчёт. Администратор настраивает и публикует, но не открывает чужие попытки: такого обхода в продукте нет.
Наставник смотрит разбор вместе с игроком на его экране. Живого тренера не заменяем.
Покупатель — сегмент, не клиент. Алабуга — автор кейса.
Переход: «Почему одинаковые ходы дают одинаковый исход.»""")

    # --- 8 ---
    s = new_slide(prs)
    eyebrow(s, "Почему этому можно доверять")
    headline(s, "Одинаковые действия на той же версии дают тот же исход", h=0.95, size=27)
    boxes = [
        ("Интерфейс", "Игрок выбирает ход. Администратор публикует версию. Фразы сохраняются как есть."),
        ("Правила переговоров", "Допустимость пакета, раскрытие фактов, полномочия и полезность считает учебный движок."),
        ("Сохранённый разбор", "Отчёт строится по событиям попытки. Повтор — новая попытка той же публикации."),
    ]
    for i, (title, body) in enumerate(boxes):
        x = 0.45 + i * 4.2
        add_rect(s, x, 1.65, 4.05, 2.55, WHITE, LINE)
        add_rect(s, x + 1.7, 1.82, 0.7, 0.7, TEAL)
        add_text(s, x + 1.7, 1.95, 0.7, 0.5, str(i + 1), size=20, color=WHITE, bold=True, name="Segoe UI", align="center")
        add_text(s, x + 0.25, 2.65, 3.55, 0.4, title, size=18, color=INK, bold=True, name="Segoe UI")
        add_text(s, x + 0.25, 3.1, 3.55, 0.9, body, size=14, color=BODY)
        if i < 2:
            add_text(s, x + 3.85, 2.55, 0.45, 0.4, "→", size=22, color=TEAL, bold=True, align="center")
    add_rect(s, 0.45, 4.45, 12.4, 2.35, WHITE, LINE)
    add_text(s, 0.7, 4.65, 12.0, 0.35, "Зачем это игроку", size=16, color=TEAL, bold=True, name="Segoe UI")
    add_text(s, 0.7, 5.1, 12.0, 0.7, "Можно открыть ход и сверить вывод. Те же сохранённые действия на той же версии не меняют исход сами по себе.", size=16, color=BODY)
    add_text(s, 0.7, 5.9, 12.0, 0.65, "Веб, Fastify, React, SQLite. Локальный запуск; остановка и новый старт сохраняют попытку. Это не публичный сайт.", size=14, color=MUTED)
    footer(s, 8)
    add_notes(s, """4:30–4:55. Три шага: экран, правила, сохранённый разбор.
Польза для человека: исход можно проверить по ходу.
Стек — одна строка. Локальный запуск, не сайт. Перезапуск с сохранением попытки измерен на одном Windows-ПК, не на любой системе.
Переход: «Что уже можно пройти и что ещё впереди.»""")

    # --- 9 ---
    s = new_slide(prs)
    eyebrow(s, "Границы MVP")
    headline(s, "Выбор действий работает сейчас. Свободный диалог — впереди", h=0.75, size=26)
    add_rect(s, 0.45, 1.65, 6.1, 5.15, WHITE, LINE)
    add_rect(s, 0.45, 1.65, 6.1, 0.55, TEAL, rounded=False)
    add_text(s, 0.7, 1.75, 5.6, 0.4, "Работает сейчас", size=18, color=WHITE, bold=True, name="Segoe UI")
    now = [
        "Две семьи сценариев с ветвлением: закупка и нагрузка.",
        "Шесть настроек, проверка и публикация версии.",
        "Выбор действий, последствия, отказ или сделка.",
        "Разбор по сохранённым ходам и повтор ситуации.",
        "Локальный Windows-запуск: без модели и без платного API.",
    ]
    y = 2.4
    for line in now:
        add_text(s, 0.75, y, 5.5, 0.7, "●  " + line, size=15, color=BODY)
        y += 0.8
    add_rect(s, 6.75, 1.65, 6.1, 5.15, WHITE, LINE)
    add_rect(s, 6.75, 1.65, 6.1, 0.55, WHITE, LINE)
    add_rect(s, 6.75, 1.65, 0.12, 5.15, MUTED, rounded=False)
    add_text(s, 7.05, 1.75, 5.5, 0.4, "Следующий этап", size=18, color=MUTED, bold=True, name="Segoe UI")
    nxt = [
        "Свободный текст и AI-оппонент — не в этом демо.",
        "Генерация сценария моделью — не в этом демо.",
        "Модель Qwen ещё не встроена и не проверена.",
        "Публичный сайт и запуск на чужом компьютере не проверялись.",
        "Сроки этих шагов не назначаем.",
    ]
    y = 2.4
    for line in nxt:
        add_text(s, 7.1, y, 5.45, 0.7, "○  " + line, size=15, color=MUTED)
        y += 0.8
    footer(s, 9)
    add_notes(s, """4:55–5:20. Граница после показанной ценности, не открытие питча.
Сейчас игрок выбирает действие из списка. Свободный текст и Qwen — следующий этап, не текущая возможность. Скачанная модель сама по себе продукт не включает.
Переход: «Давайте пройдём прототип.»""")

    # --- 10 ---
    s = new_slide(prs)
    eyebrow(s, "Демонстрация")
    headline(s, "Пройдите прототип: настройка, переговоры, разбор", h=0.85, size=28)
    add_text(s, 0.45, 1.5, 12.4, 0.7, "Отрепетируйте сложный разговор до реальной встречи. Выбор действий, без ключей и без модели.", size=18, color=BODY)
    add_rect(s, 0.45, 2.4, 7.5, 4.3, WHITE, LINE)
    add_text(s, 0.7, 2.6, 7.05, 0.4, "Материалы для жюри", size=16, color=TEAL, bold=True, name="Segoe UI")
    add_text(s, 0.7, 3.15, 7.05, 0.7, "Одна страница: исходники, запуск, презентация и описание продукта.", size=16, color=BODY)
    add_link(s, 0.7, 3.9, 7.05, 0.45, "Открыть страницу материалов",
             "https://github.com/AiratBastanov/TalkNFace/blob/docs/organizer-presentation-01/docs/submission/README.md",
             size=18)
    add_text(s, 0.7, 4.5, 7.05, 1.8, "Ссылка ведёт в репозиторий. Анонимно он сейчас не открывается: нужен доступ владельца или ZIP. Это не публичный сайт продукта.", size=15, color=MUTED)
    add_rect(s, 8.15, 2.4, 4.7, 4.3, TEAL)
    add_text(s, 8.4, 2.65, 4.25, 0.7, "После запуска на этом компьютере", size=16, color=WHITE, bold=True, name="Segoe UI")
    add_text(s, 8.4, 3.5, 4.25, 2.6, "127.0.0.1:3100/admin\n\nТолько здесь, не удалённое демо.\nСвой пароль.\nМодель не нужна.", size=18, color=WHITE)
    footer(s, 10)
    add_notes(s, """5:20–5:40, затем живой показ 3–5 минут. Вместе с речью ориентир 8–12 минут. Официальный лимит мероприятия не выдумываем: его проверяет владелец.
Живой показ — настроенная плановая поставка, не эталон со слайда 4: дружелюбный тон, доходность, пакет 95 / 40% / 50, затем «Повторить ту же ситуацию». Маршрут в DEMO_GUIDE_RU.
Если сервер недоступен: слайды 3, 1, 4 и 6.
Контактов команды нет — не выдумывайте. QR нет: публичного адреса нет, localhost в код не кладём.""")

    # --- 11 appendix ---
    s = new_slide(prs)
    eyebrow(s, "Приложение А")
    headline(s, "Как решение закрывает постановку хакатона", h=0.85, size=26)
    rows = [
        ("Аудитория и проблема", "Закупщик и руководитель; разрыв между теорией и выбором под давлением."),
        ("Ценность формата", "Повтор в том же контексте и разбор своих ходов. Не замена тренера."),
        ("Механики и путь", "Настройки, публикация, подготовка, ходы, исход, разбор, повторная попытка."),
        ("Конфигурация", "Шесть полей администратора. Невалидная цель не публикуется."),
        ("Сценарии", "Две полноценные семьи: поставка и нагрузка. Третьей отрасли нет."),
        ("Обратная связь", "Сделка отдельно от процесса; ссылка на сохранённое действие."),
        ("Прототип и запуск", "Локальный запуск на Windows по инструкции. Публичной ссылки нет."),
        ("Граница MVP", "Выбор действий, без AI. Свободный диалог — следующий шаг."),
    ]
    for i, (k, v) in enumerate(rows):
        y = 1.5 + i * 0.65
        add_rect(s, 0.45, y, 3.6, 0.58, TEAL_SOFT, TEAL_SOFT)
        add_text(s, 0.6, y + 0.12, 3.3, 0.38, k, size=13, color=TEAL_DARK, bold=True, name="Segoe UI")
        add_rect(s, 4.15, y, 8.7, 0.58, WHITE, LINE)
        add_text(s, 4.3, y + 0.12, 8.4, 0.38, v, size=14, color=BODY)
    footer(s, 11, "Приложение · не основной питч")
    add_notes(s, """Приложение. Показывайте, если жюри просит трассировку к ТЗ.
Источники: PDF с.2–7, README, DEMO_GUIDE, G5/G6/G8/clean-machine.
Опциональные геймификация «уровней персонажа» и публичный деплой не реализованы и не красились как готовые.""")

    # --- 12 appendix ---
    s = new_slide(prs)
    eyebrow(s, "Приложение Б")
    headline(s, "Короткие ответы: баллы, AI, данные, запуск", h=0.85, size=26)
    qa = [
        ("Что значит 100?", "Зачтены применимые проверки этой попытки. Это не компетенция человека и не деньги."),
        ("Почему не квиз?", "Пакет, полномочия и раскрытие фактов зависят от порядка ходов. Отказ и слабая сделка — валидные финалы."),
        ("Где AI?", "В показанном продукте его нет. Qwen задуман для более свободного диалога на тех же правилах сделки."),
        ("Данные", "Локальная база. Регистрации игрока нет. Чужой адрес попытку не открывает. Это локальный запуск, не публичный сайт."),
        ("Как запустить", "Prepare и Start -Port 3100. Нужны сеть на первую установку Node/npm и свой пароль администратора."),
        ("Что не проверено", "Linux и macOS, другой браузер, публичный сайт, чужой компьютер жюри, качество модели."),
    ]
    for i, (q, a) in enumerate(qa):
        x = 0.45 + (i % 2) * 6.4
        y = 1.5 + (i // 2) * 1.8
        add_rect(s, x, y, 6.2, 1.65, WHITE, LINE)
        add_text(s, x + 0.22, y + 0.12, 5.75, 0.4, q, size=15, color=TEAL, bold=True, name="Segoe UI")
        add_text(s, x + 0.22, y + 0.55, 5.75, 0.95, a, size=14, color=BODY)
    footer(s, 12, "Приложение · не основной питч")
    add_notes(s, """Приложение для вопросов.
Не уходите в CUDA, QLoRA, хеши гейтов и миграции.
Если спросят лицензию: файла LICENSE в репозитории нет, решение за владельцем.
Если спросят команду: состав и контакты в материалах не подтверждены.""")

    PPTX.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(PPTX))
    print(f"Wrote {PPTX} with {len(prs.slides)} slides")


if __name__ == "__main__":
    build()
