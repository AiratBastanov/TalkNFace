# APP_ORGANIZER_PRESENTATION_AND_REPOSITORY_01

**VERDICT: DELIVERED locally on `docs/organizer-presentation-01`. Remote push recorded at the end of this receipt after it is performed. Not a public submission, not a merge, not FULL_AI_MVP.**

## Baseline

| | |
| --- | --- |
| Teammate checkout | `C:/Users/Булат/TalkNFace-presentation` |
| Origin | `https://github.com/AiratBastanov/TalkNFace.git` (no credentials in URL) |
| Application base | `origin/feature/app-qwen-independent-01` @ `bb92b256ba55c72faebb69ec13a2407383bff959` |
| Presentation branch | `docs/organizer-presentation-01` created `--no-track` from that base |
| Historical main | `2034687f6f22b2973935f2c9c30bc9380c88b071` (not modified) |
| Owner filesystem | not accessed |

Git `safe.directory` was set only in the process environment (`GIT_CONFIG_COUNT`), not as a global config change.

## Artifacts

| File | SHA256 | Bytes |
| --- | --- | ---: |
| `docs/submission/TALKNFACE_PRODUCT_PITCH_RU.pptx` | `9114aba2ae0d05fc949dae4e7ec8af52bd3ff66a1211cbb13327aec1cb69f8f8` | 226476 |
| `docs/submission/TALKNFACE_PRODUCT_PITCH_RU.pdf` | `ee83db0204b6a8eb2b4e84d67335c418416e1db3baae461983205633f487732e` | 427787 |

12 слайдов (10 основных + 2 приложения). PPTX редактируемый (текст и фигуры). PDF экспортирован Microsoft PowerPoint COM, 12 страниц, 16:9 (`960×540` pt). Контрольные PNG 1920×1080 в игнорируемом `.tmp/organizer-presentation-01/`.

Сборка: `docs/submission/authoring/build_pitch.py` в изолированном `.tmp/organizer-presentation-01/venv`.

## Checks

- Кадры слайдов просмотрены целиком: кириллица на месте, сиротские переносы заголовков убраны, мелкие коллажи сняты.
- PPTX и PDF: 12 слайдов, тот же порядок, те же заголовки.
- Скриншоты — кропы committed UI; текст интерфейса не подменялся. Новых сессий приложения на этой машине не запускали: существующих кадров G5/G6/G8/clean-machine достаточно. Отсутствие нового запуска не сертифицирует Windows 10 этого ПК.
- Анонимный GitHub / API / ZIP feature-ветки: HTTP 404 (2026-09-28). QR нет.
- Команды Prepare/Start/Stop в README, DEMO_GUIDE и слайде 10 совпадают.
- Diff к базе приложения: только README, DEMO_GUIDE, `docs/submission/**`, этот receipt. `apps/`, `packages/`, `scripts/`, lockfile, ML — без изменений.

## AI status (unchanged)

В показанном продукте нет готовой встроенной и quality-validated модели. Guided + детерминированный движок. Обучение Qwen не инспектировалось.

## Missing metadata (owner)

- Имена команды, логотип, контакты — не подтверждены, на слайды не выдумывались.
- LICENSE отсутствует.
- Анонимный доступ к репозиторию закрыт.
- Интеграция презентации во ветку приложения и сдача организаторам — не выполнялись.

## Push / upstream

Заполняется после `git push -u origin HEAD:refs/heads/docs/organizer-presentation-01`.
