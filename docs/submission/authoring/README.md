# Сборка продуктовой презентации

Колода строится из **официального шаблона ЛЦТ 2026** (37 слайдов, рядом с корнем репозитория или на Рабочем столе). Файл шаблона в Git не кладётся и скриптом не перезаписывается. Берутся готовые слайды-холсты, лишние примеры и библиотеки иконок удаляются.

Картинки продукта режутся из уже сохранённых экранов приложения, без правки текста интерфейса. Знак Алабуги копируется из слайда логотипов шаблона. Шрифт темы — Montserrat через тему PowerPoint; файлы шрифтов не скачиваются и в репозиторий не кладутся.

Изолированное окружение (не ставить в приложение и не менять lockfile):

```powershell
python -m venv .tmp\organizer-presentation-01\venv
.\.tmp\organizer-presentation-01\venv\Scripts\python.exe -m pip install -r docs\submission\authoring\requirements.txt
.\.tmp\organizer-presentation-01\venv\Scripts\python.exe docs\submission\authoring\build_pitch.py
```

`build_pitch.py` вызывает `assemble_template.ps1` (копия шаблона, 14 холстов), затем заполняет тексты. PDF и контрольные PNG — `export_pitch.ps1` через COM установленного Microsoft PowerPoint.
