# Арена переговоров / Negotiation Arena

Тренажёр для начинающих закупщиков и руководителей: администратор задаёт контекст, проверяет и публикует ситуацию; игрок готовится, ведёт переговоры, получает разбор по сохранённым действиям и начинает повторную попытку. Доступны S1 «Поставка» и S2 «Срочная задача и нагрузка». **Guided-демо без AI**: игрок выбирает действия, результат вычисляет детерминированная учебная модель. Это не оценка реальных компетенций.

## Запустить на Windows

Проверяемый путь: **Windows 11 x64, Windows PowerShell 5.1, Google Chrome**, обычная учётная запись без прав администратора. Для первой установки нужен HTTPS-доступ к **nodejs.org**, **registry.npmjs.org**, **github.com** и доменам GitHub Releases (`release-assets.githubusercontent.com`, возможен `objects.githubusercontent.com`). Chrome нужен для показа; Git нужен только для получения исходников. Python, CUDA, Docker, Qwen, ключи AI, компилятор C++ и глобальные npm-пакеты не нужны.

Получите именно feature-ветку (эта работа не объединена с main):

```powershell
git clone --single-branch --branch feature/app-qwen-independent-01 https://github.com/AiratBastanov/TalkNFace.git "Negotiation Arena"
Set-Location "Negotiation Arena"
```

Либо скачайте [ZIP feature-ветки](https://github.com/AiratBastanov/TalkNFace/archive/refs/heads/feature/app-qwen-independent-01.zip), распакуйте и откройте PowerShell в корне с `package.json`. Запуск не использует `.git`. Пути с пробелами поддерживаются; AI/model-каталоги запуску не нужны.

Выполните **две команды**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Prepare
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Start -Port 3100
```

При первом Prepare дважды введите скрытый пароль администратора (12–256 символов). Придумайте свой: общего/стандартного пароля нет. Скрипт сохраняет **только scrypt-хеш**, устанавливает зависимости по lockfile, собирает production и проверяет SQLite. Постоянный сервер этот шаг не запускает. Прерванную подготовку можно повторить; БД и существующий пароль сохраняются. Повторный Prepare выполняет `npm ci` заново, без обновления lockfile.

Откройте **http://127.0.0.1:3100/admin**, введите выбранный пароль. Игровой вход — **http://127.0.0.1:3100/**, регистрация не нужна. Пользуйтесь `127.0.0.1`, не заменяйте его на `localhost`: Origin проверяется точно. Без `-Port` используется 3000; занятый порт вызывает отказ. Скрипт запускает реальный Fastify/React production в фоне, только на loopback, без watch.

Остановка и последующий запуск **сохраняют данные**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Status
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Stop
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Start -Port 3100
```

Status только читает состояние. Stop обращается к управляющему каналу именно этого checkout, закрывает HTTP/SQLite и никогда не завершает процесс по PID из старого файла. После аварии снова выполните Start: SQLite восстановит WAL, старое status-состояние не даёт права убить чужой процесс.

[Сценарий показа на русском, 3–5 минут](docs/DEMO_GUIDE_RU.md).

## Runtime и воспроизводимость

Windows launcher принимает **ровно Node.js 24.21.0 x64 и npm 11.19.0**. Подходящая установка из текущего PATH используется автоматически; другой Node не принимается. Иначе Prepare скачивает [официальный portable ZIP](https://nodejs.org/download/release/v24.21.0/node-v24.21.0-win-x64.zip), сверяет SHA256 с [официальными SHASUMS](https://nodejs.org/download/release/v24.21.0/SHASUMS256.txt) и закреплённым `158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541`, проверяет пути/типы записей и распаковывает в `.tools/arena-runtime/`. При повторном использовании файлы runtime сверяются с этим ZIP. MSI, системные настройки, постоянный PATH, execution policy и права доступа Windows не меняются. `-ExecutionPolicy Bypass` относится только к указанному процессу PowerShell.

Можно явно передать `-NodePath 'C:\portable\node.exe'` к каждой команде. Требуется тот же bundled npm. Общий developer runtime-check допускает `>=24.0.0 <25`; **сертифицируемый Windows launcher намеренно строже**.

Установка: `npm ci --ignore-scripts --include=dev --no-audit --no-fund`, затем только закреплённый `prebuild-install` для `better-sqlite3@12.11.1`. Это исключает fallback на Python/node-gyp. Других Windows install hooks в текущем lockfile нет; изменение списка требует проверки. Затем проверяются `npm ls --all`, версии по lockfile, загрузка native SQLite, неизменность исходников/lockfile и выполняется `npm run build`. Кеш создаётся в `.tools/arena-npm-cache`, глобальные настройки npm не нужны. Первичная online-установка проверяется с пустым кешем; offline-установка с неполным кешем не обещается. После подготовки запуск/игра работают без внешних сервисов.

Лимиты: суммарная загрузка Node 300 с, проверка/распаковка 120 с, npm ci + native prebuilt 300 с, build 300 с, startup 20 с, backup/restore 60 с. Измерения свежего checkout — в [receipt воспроизводимости](docs/gates/APP_CLEAN_MACHINE_REPRODUCIBILITY_01.md); скорость зависит от сети/ПК, время ввода пароля туда не входит.

## Данные, пароль, backup

Все локальные артефакты внутри checkout игнорируются Git:

| Путь | Назначение |
| --- | --- |
| `.local/arena-demo/arena.sqlite` и WAL/SHM | Публикации, общий черновик, попытки, ходы, подготовка, replay и G8 access records |
| `.local/arena-demo/backups/` | Проверенные SQLite backups |
| `.local/arena-demo/server.json`, `prepared.json`, `server.log` | Несекретное управление процессом, fingerprints сборки, безопасный лог |
| `.local/arena-config/admin.json` | Секретная локальная конфигурация с хешем пароля |
| `.tools/arena-runtime/`, `.tools/arena-npm-cache/` | Portable runtime и кеш установки |

Схема config: `{"schema":1,"adminPasswordHash":"<сгенерированный scrypt-хеш>"}`. Формат хеша — существующий G8 `scrypt$32768$8$1$<salt-hex>$<digest-hex>`. Скрипт создаёт его сам, не печатает и не заменяет при обычной подготовке. `.env`, `ADMIN_PASSWORD_HASH`, `HOST`, `DATABASE_PATH` и внешние deployment overrides этим launcher не используются: источник настроек один. Не отправляйте `.local`/backups в Git или публичные материалы.

Явная смена пароля при остановленном сервере:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Stop
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -SetAdminPassword
```

Смена хеша делает прежние admin-сессии недействительными. Отсутствующий/повреждённый config запрещает Start; Prepare не перезаписывает повреждённый config. Только для автоматизации есть `-PasswordFromStdin`: пароль передаётся UTF-8 через stdin из памяти/секретного хранилища, никогда через аргумент или литерал в истории команд. Обычный пользователь использует скрытый prompt.

Backup работает и при запущенном демо. Используется [SQLite backup API better-sqlite3](https://github.com/WiseLibs/better-sqlite3/blob/master/docs/api.md#backupdestination-options---promise), затем `integrity_check`/`foreign_key_check`, а не копирование открытого файла:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Backup
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Status
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Stop
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Restore 'ID-из-Backup-или-Status'
```

Restore принимает только ID своего backup, проверяет его и сохраняет прежнюю БД в `before-restore-*`. Закройте сторонние SQLite-редакторы. Публикации/попытки возвращаются к снимку. Чтобы restore не оживлял отозванный доступ, сессии снимка сохраняют доступ только если они ещё действуют в текущей БД, без продления срока; отсутствующие/отозванные сессии отзываются и в восстановленной БД. Backups не заменяют config/пароль.

**Явный сброс демо** при остановленном сервере:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -ResetDemoData
```

Команда показывает точный путь, сохраняет `before-reset-*` backup и создаёт пустую БД через SQLite. Пароль и backups остаются. Symlink/junction и выход за локальный каталог запрещены. Сброс никогда не выполняется автоматически. После сброса начните новую игру; прежние cookie не дают доступа к удалённым попыткам.

## Если запуск не удался

- Нет сети: разрешите перечисленные HTTPS-источники и повторите Prepare. При недоступном native prebuilt установка останавливается, не запускает Python. БД/config не удаляются.
- Неподходящий NodePath: укажите точные Node/npm или уберите параметр для автоматической загрузки.
- Повреждённый/неполный runtime: переместите **только `.tools/arena-runtime`** в другой локальный каталог, повторите Prepare. `.local` сохраняйте.
- Ошибка npm ci/несовпадающий lockfile: используйте согласованный checkout; не применяйте npm install/audit-fix как способ починки этого пути.
- Прерванный Prepare/build: повторите Prepare. Start проверяет fingerprints и не использует частичную сборку.
- Порт занят: остановите занимающую его программу самостоятельно или задайте другой Port; launcher не убивает чужие процессы.
- БД заблокирована/недоступна: закройте SQLite-редактор/другой экземпляр, проверьте доступность каталога. Не удаляйте БД/WAL для восстановления.
- Неясное состояние: Status, затем Verify; startup log — `.local/arena-demo/server.log`, справка — Help.

## Архитектура и границы

Один production Fastify-процесс обслуживает React/Vite и API с одного origin. SQLite/better-sqlite3 хранит данные; миграции 1–5 применяются без сброса. Пять явных workspaces: `apps/server`, `apps/web`, `packages/contracts`, `packages/domain`, `packages/scenarios`. `packages/ai` вне installation/runtime; обучающие данные и модели не нужны. Контекст детерминированно компилируется из шести настроек, проверяется движком и публикуется отдельной неизменяемой версией. Разбор G6 выводится из сохранённых событий/фраз; replay — отдельная попытка той же версии.

G8: HttpOnly/SameSite=Strict cookie, владение попытками, CSRF, Origin/Fetch Metadata, rotation/logout/expiry. UUID — адрес, не авторизация. Player access: 24ч idle/7д absolute; admin: 30мин idle/8ч absolute. GET не продлевает доступ. Потеря cookie/выход/истечение срока не имеют восстановления аккаунта; данные остаются в БД. Перезапуск с прежним хешем сохраняет действующий доступ. Общий лимит входа — 10 попыток за 15мин, включая успешные. trustProxy не включается.

Этот путь — **loopback HTTP на доверенном локальном ПК**. Публичное размещение, HTTPS/reverse proxy, Linux/macOS/ARM, live AI, полные G5/G6/G7/G8 и финальная сдача хакатона не сертифицированы. Публичный listener и туннели здесь не предусмотрены.

Developer-команды с Node 24: `npm ci`, `npm run build`, `npm run typecheck`, `npm test`; прежний `npm run test:e2e` использует установленный Chrome и отдельные тестовые БД. `npm start` — прежний developer entry с .env/переменными; для показа используйте Windows launcher. Новый bounded тест launcher: `node tests/clean-demo/failures.mjs`; acceptance: `node tests/clean-demo/acceptance.mjs <путь-к-чистому-checkout>` (случайный пароль только в памяти теста).

Принятые исторические свидетельства: [G5](docs/gates/APP_G5_CONTEXT_CONFIGURATION_01.md), [G6](docs/gates/APP_G6_DETERMINISTIC_FEEDBACK_01.md), [G8](docs/gates/APP_G8_ACCESS_BOUNDARY_01.md). Исторический [PARTIAL read-boundary incident](docs/gates/APP_AUDIT_AND_QWEN_INDEPENDENT_SLICE_01.md) сохраняется ровно как записан, не переклассифицируется и не является доказательством загрязнения gradient-training. Frozen plans/PDF и training handoff не изменяются.
