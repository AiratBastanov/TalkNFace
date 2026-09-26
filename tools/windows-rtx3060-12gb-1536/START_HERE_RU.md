# Проверка RTX 3060 12 ГБ на компьютере друга

**Уже выполненная кампания `1c270adba77545720fa33bcee0e24f7d6f46e55d`: только исправление упаковки и сертификации.** GPU-обучение повторять нельзя. В существующем checkout с исходными `.tmp`, адаптером и ZIP выполните:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'git pull failed' }
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-rtx3060-12gb-1536\RUN-RTX3060-12GB-REMOTE.ps1 -RepoRoot . -PackageOnly
```

Эта команда вызывает только фазу 05 и verifier: без CUDA, загрузки модели, подготовки TRAIN или фазы 04. Она проверяет исторический training commit отдельно от нового packaging commit, реальный origin и чистоту Git, исходные доказательства и отсутствие изменений training/model/data/config в истории исправления. Ожидаются `archive_integrity: PASS`, `certified_training_pass: true` и исходный training verdict `RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_SMOKE_PASS`. Полное обучение остаётся **NOT STARTED**.

Старый ZIP автоматически сохраняется в `.tmp/rtx3060-12gb-targeted-1536-smoke/packaged-history/<SHA256>.zip` с проверкой хеша и сообщением `PRESERVED`. Новый результат и SHA256 печатаются в консоль. Отправьте новый `handoff-results/RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip`. Не удаляйте `campaign-started.json`, не меняйте исходные JSON, модель или адаптер. Если проверка не прошла, сохраните вывод и файлы; это не разрешение повторить обучение.

**Ниже сохранена историческая инструкция первоначального запуска. Для уже выполненной кампании её команды подготовки и обучения не применяются.**

Codex не нужен. Нужны Windows 10/11 x86-64, **настольная RTX 3060 12 ГБ** (не 8 ГБ, не Ti, не Laptop), Git для Windows, **Python 3.12.10 x64** и рабочий драйвер NVIDIA. Установите отсутствующие Git/Python/драйвер вручную. Для Python включите компонент launcher `py`; менять PATH необязательно. Скрипты не устанавливают системные компоненты, CUDA Toolkit, Visual Studio, WSL или Docker, не меняют pagefile, права, реестр и постоянную execution policy.

Откройте обычный **64-разрядный Windows PowerShell**, без прав администратора. Желательно иметь 30 ГиБ свободного места на диске проекта. Перед кампанией закройте игры и программы, использующие GPU: нужно >=10800 МиБ свободной VRAM по nvidia-smi, >=10500 МиБ по CUDA и >=12 ГиБ доступной физической RAM. Скрипт сам проверит модель GPU, обе ёмкости >=12000 МиБ и compute capability 8.6.

Получите от владельца **Qwen3-4B.tar**, **Qwen3-4B.tar.sha256** и эту инструкцию. Положите оба файла рядом на рабочий стол. SHA256 нового TAR:

`D69F99B94DD0E5346F5882F6ED327BEE925D060659648FB75877C1C0D5FCE09A`

Sidecar проверяется автоматически. Если есть другой проверенный TAR, можно явно передать `-TransportSha256 <64-значный SHA256>`. Без sidecar и явного параметра ожидается исторический SHA256 `30FAB06F571F6B7F0B62342045BD6B10C2D65DE2EDA8CAEBC32E7BAF56CFD697`. После проверки TAR каждый файл модели всё равно сверяется с исходным model-lock.

Склонируйте исходники одной строкой (если папка уже есть, используйте отдельный проверенный checkout и не перезаписывайте чужие изменения):

```powershell
git clone --branch main https://github.com/AiratBastanov/TalkNFace.git "$env:USERPROFILE\Desktop\Alag"; if ($LASTEXITCODE -ne 0) { throw 'git clone failed' }
```

Перейдите в проект:

```powershell
Set-Location -LiteralPath "$env:USERPROFILE\Desktop\Alag"
```

Подготовьте окружение, импортируйте/проверьте модель и измерьте TRAIN. Эта команда **не загружает веса Qwen для вычислений и не запускает кампанию обучения**. Она выполняет только маленькую проверку CUDA/NF4 и tokenizer/compiler-подготовку:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-rtx3060-12gb-1536\RUN-RTX3060-12GB-REMOTE.ps1 -RepoRoot . -ModelArchive "$env:USERPROFILE\Desktop\Qwen3-4B.tar" -PrepareOnly
```

Дождитесь `PREPARE ONLY complete`. Подготовка должна подтвердить 8000 записей, максимум 1421, длины `[1396,1393,1391,1388]` и `[1421,1408,1406,1402]`, reload 1387. Настроенный предел — 1536; реального примера длиной 1536 здесь нет. Повтор `-PrepareOnly` проверяет и использует готовое состояние. Окружение не переустанавливается каждый раз.

После успешной подготовки запустите **одну** кампанию этой строкой:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-rtx3060-12gb-1536\RUN-RTX3060-12GB-REMOTE.ps1 -RepoRoot .
```

Это восемь TRAIN-микробатчей, два обновления оптимизатора и загрузка сохранённого адаптера в новом процессе. Полное обучение и оценка качества не запускаются. Не закрывайте окно; скрипт печатает активную фазу, путь к журналу, число обработанных записей/микробатчей и измерения. У каждой фазы есть фиксированный предел времени.

При ошибке сохраните все файлы. **Не удаляйте маркеры, адаптеры или окружение.** Повтор допускается только после подтверждённого отказа до загрузки модели; это определяет скрипт. После загрузки/неясного прерывания повторного обучения не будет. Вернуть диагностический результат отдельно можно так:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-rtx3060-12gb-1536\RUN-RTX3060-12GB-REMOTE.ps1 -RepoRoot . -PackageOnly
```

Для просмотра плана без установок, загрузок, файловых изменений и CUDA-вызовов:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-rtx3060-12gb-1536\RUN-RTX3060-12GB-REMOTE.ps1 -RepoRoot . -DryRun
```

Если локального TAR нет, только по явному выбору можно использовать ограниченную по времени загрузку закреплённой ревизии из Hugging Face:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-rtx3060-12gb-1536\RUN-RTX3060-12GB-REMOTE.ps1 -RepoRoot . -AllowModelDownload -PrepareOnly
```

Не нужно повторять сетевую ошибку бесконечно, менять TLS или версии пакетов. Частичные загрузки сохраняются для разбора. Подходящая локальная модель используется без обращения к Hugging Face. Каталог с неизвестной или несовпадающей моделью автоматически не перезаписывается.

Верните владельцу **только**:

`Alag\handoff-results\RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip`

ZIP не содержит весов, строк датасета, промптов, массивов токенов или ключей. Успешная проверка целостности ZIP сама по себе не означает успешного обучения. Владелец проверит его скриптом `verify_result.py`, который идёт в репозитории. PASS_TIGHT_MEMORY не разрешает полное обучение; обычный PASS тоже требует отдельного решения владельца.

Все пути вычисляются относительно реально запущенных скриптов. Можно выбрать другую папку или диск, включая путь с кириллицей и пробелами; переданный `-RepoRoot` должен указывать на тот же checkout. Старые RTX3070 scratch, ZIP и venv с другого компьютера не нужны. Старый внешний materializer больше не запускайте.
