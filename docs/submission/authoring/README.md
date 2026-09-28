# Сборка продуктовой презентации

Источник слайдов: `build_pitch.py`. Картинки режутся из уже сохранённых экранов приложения, без правки текста интерфейса.

Изолированное окружение (не ставить в приложение и не менять lockfile):

```powershell
python -m venv .tmp\organizer-presentation-01\venv
.\.tmp\organizer-presentation-01\venv\Scripts\python.exe -m pip install -r docs\submission\authoring\requirements.txt
.\.tmp\organizer-presentation-01\venv\Scripts\python.exe docs\submission\authoring\build_pitch.py
```

PDF и контрольные PNG экспортируются установленным Microsoft PowerPoint через COM, см. `export_pitch.ps1`. Шрифты системы: Segoe UI и Calibri. Файлы шрифтов в репозиторий не кладём.
