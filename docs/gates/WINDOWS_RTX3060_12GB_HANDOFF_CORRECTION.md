# WINDOWS_RTX3060_12GB_HANDOFF_CORRECTION

**VERDICT: WINDOWS_RTX3060_12GB_HANDOFF_CORRECTION_PASS**

Это завершённое исправление исходников и проверенная передача инфраструктуры. **RTX3060 hardware execution: NOT RUN. Full training: NOT STARTED.** VRAM RTX3060 и качество обученной модели этим verdict не сертифицируются.

Авторитетный checkout: ветка `main`, origin `https://github.com/AiratBastanov/TalkNFace.git`, исходный HEAD `9fd7f2cd14c22c111c1d99d6e9c29eb5554575b2`; после ограниченного fetch — 0/0. До исправления staged/unstaged tracked-изменений не было. Найдено 30 untracked исходников нового gate и 17 скопированных игнорируемых pyc. Все 47 файлов сопоставлены с точным поведением прерванного materializer, сохранены вместе с SHA256-инвентарём в `.tmp/rtx3060-handoff-recovery/20260925T101013Z/`. RTX3060 campaign/runtime/adapters/result до восстановления отсутствовали. Чужие изменения не обнаружены и не перезаписывались; регрессия с отдельным пользовательским файлом проверяет его сохранность.

Причина сбоя подтверждена по реальным файлам: внешний installer искал цикл `quantization, lora, activation_offload, host_memory, remote_resources`, тогда как принятый `control.py` начинает его с `seed, model, train`. Ошибка возникала после копирования каталога и изменения config, до Git add/commit/push. Исправление выполнено непосредственно в новом tracked gate; старый materializer объявлен устаревшим.

Полная цепочка теперь включает реальные 00–05: read-only prerequisites, создание/проверку venv, model-lock verification и безопасный TAR import, полное измерение TRAIN, одну кампанию и свежий reload, затем упаковку и независимую проверку результата. Удалены runtime-зависимости от старого RTX3070, setup-stubs и неверный ToolRoot. Исторические config/decision остаются read-only ссылками. Все 61 исходный файл исторических gate неизменны, четыре runtime/model lock/requirements файла сохранены побайтно.

Одна политика в `config.json` задаёт desktop RTX3060/sm86, physical/CUDA capacity >=12000 МиБ, nvidia free >=10800 МиБ, CUDA free >=10500 МиБ, доступную RAM >=12 ГиБ, стоп-порог 6 ГиБ и pagefile growth <=256 МиБ. Порог двух CUDA boundaries сохранён: >=512 МиБ — кандидат PASS, [256,512) — PASS_TIGHT_MEMORY, ниже — failure. NV telemetry, allocator allocated/reserved, CUDA free, WDDM shared/dedicated, RAM и pagefile проверяются отдельно. Missing evidence не заменяется нулём/успехом.

Сохранён весь принятый эксперимент: исходные Qwen3-4B pins; NF4/double quant/FP16; CUDA:0, SDPA; q_proj+v_proj, r8/alpha16/dropout0.05/bias-none; 2 949 120 trainable parameters, 72 A и 72 B; batch1/accumulation4/two updates; paged_adamw_8bit, LR0.0002; исходные seeds, checkpointing и host activation offload; completion-only JSON+EOS; без truncation/packing. Предел 1536 отделён от фактических длин, схема `observed_max_length` сохранена.

Долговечный ledger и эксклюзивные маркеры создаются до model load; OS lock, сведения о процессах, следы worker и адаптера исключают автоматический повтор после исполнения/неясного прерывания. Подтверждённый pre-load отказ можно повторить после исправления условия; его записи сохраняются. Все бюджеты фиксированы заранее, native failures передаются вверх, stdout не дренируется бесконечно. PrepareOnly/PackageOnly не вызывают обучение; DryRun не создаёт файлов и не запускает загрузки/установки/CUDA.

Проверки владельца:

| Группа | unittest cases | Что реально / что fixture |
|---|---:|---|
| source/recovery/policy/selection | 19 | Реальный backup и исходники; GPU/verdict — fixtures |
| environment/model | 20 | Настоящие малые TAR/файлы; pip/venv install boundaries — mocks |
| Windows PowerShell 5.1 | 11 | Реальный parser, процессы, Unicode/пробелы, exit/timeout, DryRun; orchestration install/GPU — mocks |
| campaign/result verifier | 24 | Реальная межпроцессная блокировка и ZIP; training/reload — fixtures, явно не hardware evidence |
| **Итого** | **74 PASS, 0 FAIL** | По 180 секунд на focused group; без package install/Qwen execution |

Дополнительно выполнены реальные проверки принятым owner-окружением:

- Измерены все **8000/8000 TRAIN** за ~58 секунд, maximum **1421**, truncation=0. Step 1: **1396,1393,1391,1388**; step 2: **1421,1408,1406,1402**; unused reload record: **1387**. Tokenizer hashes до/после одинаковы; audit не обнаружил eval reads или разрешённой сети.
- Реальный TRL completion collator проверил девять полных записей, маску prompt, canonical JSON/EOS; PEFT на `meta` подтвердил 2 949 120 параметров и 72+72 тензора. Qwen checkpoint loads, inference, backward, optimizer updates = **0**.
- Все десять локальных model files совпали с исходным model-lock. Исторический Desktop TAR отсутствовал, его текущий SHA256 неприменим. По последующему явному запросу владельца создан новый TAR, проверены его payload и настоящий импорт в отдельный staging (~20 секунд). Исходная модель не перезаписана.
- Реальный read-only preflight отверг owner **RTX2060 6144 МиБ / sm75** по имени, физической ёмкости и capability. Sandbox запрещал WMI; повторный read-only вызов вне sandbox подтвердил именно аппаратный отказ, без elevation/system changes.

Новый переносимый файл: `.tmp/rtx3060-12gb-targeted-1536-smoke/transfer/Qwen3-4B.tar`, **8 060 907 520 байт**, SHA256 **D69F99B94DD0E5346F5882F6ED327BEE925D060659648FB75877C1C0D5FCE09A**. Рядом `Qwen3-4B.tar.sha256`. Весов, TRAIN rows, caches, environments или credentials в новых Git-файлах нет.

ZIP результата имеет точный manifest без duplicates, только RESULT/evidence/manifest. Verifier проверяет hardware/config/source/model identity, selection и реальные microbatch lengths, два нескipped finite updates, mutation/save/fresh reload, CUDA boundaries/RAM/pagefile, явные audits и `full_training_started == false`. Archive-integrity PASS отделён от training PASS; отсутствие evidence не сертифицируется. Сырые журналы и исключения с произвольным текстом в ZIP не попадают. Python audit hooks не объявляются OS sandbox; native limitations явно документированы.

Инструкции: [START_HERE_RU](../../tools/windows-rtx3060-12gb-1536/START_HERE_RU.md), [owner handoff](../../tools/windows-rtx3060-12gb-1536/OWNER_HANDOFF_RU.md). Владелец отправляет TAR, sidecar, инструкцию и ссылку на Git. Друг возвращает только `handoff-results/RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip`.

**REAL_APPLICATION_SMOKE = NOT_APPLICABLE_WITH_REASON:** isolated training/handoff infrastructure; no application behavior changed. G3 integration, full training, quality evaluation и RTX3060 smoke на owner PC не запускались.

STOP — RTX3060 HARDWARE SMOKE AND FULL TRAINING NOT RUN ON OWNER PC.
