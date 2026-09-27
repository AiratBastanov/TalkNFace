# Qwen3-4B V1 — подготовленный Windows workflow

**НЕ ЗАПУСКАТЬ ОБУЧЕНИЕ СЕЙЧАС.** Этот handoff готовит будущий запуск после отдельного разрешения владельца. Полное обучение, inference Qwen и оценка качества в этом gate не выполняются.

Модель остаётся интерпретатором русских высказываний в существующий `PlayerMoveInterpretation`. Решения о принятии сделки, полезность, scoring и состояние переговоров остаются в детерминированном приложении. Снижение loss не разрешает G3 integration.

## Принятая основа и V1

Исторический финальный ZIP принят **до изменения tracked source** строгим старым verifier на `e3de4db26a6c4dad25dc51a6b321ff2b434d0e00`. SHA256: `2d90867e8be4960c1878effa12c3ddc20acbc1c4609ae4c952f33bf0b8e220ed`, 65 320 байт. Историческое обучение: `1c270adba77545720fa33bcee0e24f7d6f46e55d`. Полные pins и версия verifier: [accepted-baseline.json](accepted-baseline.json). Старый smoke и его allowlist не изменяются.

V1: **ровно один shuffled TRAIN epoch, 8000 строк, 8000 microbatches, 2000 успешных updates**, accumulation 4. Новый random LoRA; smoke-адаптер не читается. Checkpoint/tokenizer: `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c`, десять исходных файлов из старого model-lock.

[candidate-v1.json](candidate-v1.json) фиксирует NF4 + double quantization, FP16, `cuda:0`, SDPA, q/v only, r=8, alpha=16, dropout=.05, bias=none, 2 949 120 trainable parameters, microbatch=1. BF16/TF32, packing, truncation, CPU model-weight offload, auto device map и allocator overrides запрещены. Сохраняются Transformers pinned-host activation offload и `use_reentrant=True`; PEFT preparation не включает checkpointing повторно.

LR=.0002; seed=data_seed=20260917. Используется фактический smoke optimizer `bitsandbytes.optim.adamw.AdamW`: paged/8bit, betas=(.9,.999), eps=1e-8, **weight_decay=.01**, min_8bit_size=4096, amsgrad=false. Smoke передавал kwargs без weight_decay и получал .01 из установленного bitsandbytes; Trainer default=0 не подставляется. Gradient clipping=1.0. AMP scale=65536, growth=2, backoff=.5, interval=2000. Дополнение для full run: явный constant scheduler, warmup=0, шаг scheduler только после успешного optimizer call.

Loss: mean cross-entropy по supervised completion-токенам каждой полной записи; среднее четырёх таких losses на update. Backward каждого loss/4. Epoch loss = сумма losses committed записей / 8000, без token-weighted перераспределения. Canonical JSON, assistant EOS и допустимый template whitespace после EOS полностью сохраняются; prompt и padding имеют -100. Наличие overflow, nonfinite gradient/loss или пропущенного AMP update останавливает попытку: cursor/scheduler не продвигаются как успешные, автоматического retry нет.

Порядок: `random.Random(20260917).shuffle(range(8000))` в pinned Python 3.12.10. Полная permutation сохранена в order.json и optimizer state. Dataset не фильтруется: Prepare измеряет все 8000 записей, проверяет max=1421 и отвергает любую >1536. Сохраняется порядок вложенных ключей TRAIN contexts, влияющий на точные bytes prompt.

## Условия и пути

Обычный Windows PowerShell **5.1 x64**, чистый `main` authoritative origin. Использовать уже проверенный `.venv-qlora-remote\Scripts\python.exe` и `AlagModels\Qwen3-4B`. Никаких переустановок, pip install, загрузок модели, admin, правок PATH/ACL/registry/pagefile/drivers. Если среда или hashes расходятся, остановиться и передать диагностику владельцу. `-PythonExe` принимает конкретный `python.exe`; `py.exe` и launcher selectors не смешиваются.

Для `RunId=qwen3-4b-v1`:

| Назначение | Путь относительно checkout |
| --- | --- |
| Runtime, tokens, логи, immutable receipts | `.tmp/qwen3-4b-full-training/qwen3-4b-v1/runtime/` |
| Полные локальные resume checkpoints | `.tmp/qwen3-4b-full-training/qwen3-4b-v1/checkpoints/` |
| Финальный deployable adapter | `.tmp/qwen3-4b-full-training/qwen3-4b-v1/adapter/` |
| Sanitized diagnostic и отдельный adapter ZIP | `handoff-results/qwen3-4b-full-training/qwen3-4b-v1/` |

Все runtime/weights/ZIP игнорируются Git. Существующие smoke scratch/adapter paths не используются. Junction/symlink outputs отвергаются. Не переносить runtime между компьютерами и не редактировать run.json.

## Команды другу — НЕ ВЫПОЛНЯТЬ ДО ОТДЕЛЬНОГО РАЗРЕШЕНИЯ

Из корня существующего checkout после получения доставленного `main`. `ExecutionPolicy Bypass` ниже действует только на этот дочерний процесс PowerShell.

```powershell
$w = '.\tools\windows-rtx3060-full-training\RUN-FULL-TRAINING.ps1'
$run = 'qwen3-4b-v1'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $w
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $w -Action Prepare -RunId $run -DryRun
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $w -Action Prepare -RunId $run
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $w -Action Status -RunId $run
```

Prepare выполняет hashes/runtime validation и CPU tokenization, не загружает веса Qwen для вычислений. Help, DryRun, Status, Package также не запускают модель. После **отдельного разрешения именно нового run**:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $w -Action Start -RunId $run -AuthorizeNewRun $run
```

Никакого второго Start для существующего run. Для остановки — Ctrl+C либо из второго обычного PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $w -Action Cancel -RunId $run
```

После проверки Status и причины остановки, **явное продолжение того же run**:

```powershell
$latest = Join-Path (Join-Path '.tmp\qwen3-4b-full-training' $run) 'checkpoints\LATEST.json'
$cp = (Get-Content -LiteralPath $latest -Raw -Encoding UTF8 | ConvertFrom-Json).checkpoint
Write-Output $cp
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $w -Action Resume -RunId $run -Checkpoint $cp
```

Не повторять обучение ради packaging error. Упаковка не исполняет модель:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $w -Action Package -RunId $run
```

Получить отдельно `diagnostic-<attempt>.zip` и, только после полного завершения, `adapter-<attempt>.zip`. Проверка конкретного возвращённого файла:

```powershell
& '.\.venv-qlora-remote\Scripts\python.exe' -B '.\tools\windows-rtx3060-full-training\verify_result.py' '<полный путь к конкретному ZIP>'
```

`archive_integrity=PASS` означает целостность. `COMPLETED_UNEVALUATED` означает только полный TRAIN pass. Ни один из этих результатов не означает качество модели. `ADAPTER_INTEGRITY_ONLY` подтверждает отдельный deployable payload, не заменяет диагностический receipt. Fixture results всегда помечены `FIXTURE_ONLY`.

## Checkpoint, ошибки и продолжение

До первой microbatch сохраняется step-0000; затем checkpoint после **каждого успешного update**. Он содержит только LoRA weights/config, optimizer, constant scheduler, AMP scaler, Python/NumPy/Torch/all-CUDA RNG, epoch/step/cursor, точную permutation, run nonce, model/tokenizer/data/source/runtime/config pins, SHA256/size manifest и completion marker. Полная база не клонируется на GPU и не сериализуется.

Запись идёт в `.incomplete-*`, с flush/fsync, hash verification, CPU-десериализацией optimizer state и проверкой safetensors; затем atomic directory rename и atomic LATEST. Пока новая запись не проверена, предыдущая сохраняется. Retention: **2 verified checkpoints**, плюс временный staging. Incomplete directories не являются resume targets и сохраняются для разбора; не выбирать их и не удалять старые доказательства наугад.

Resume требует newest committed `step-NNNN` этого run. Чужой, обрезанный, повреждённый, stale, inference-only adapter или несовпадающие pins отвергаются. Поздний commit только упаковщика/документации допускается: frozen training source проверяется по своему manifest, его commit не заменяется новым HEAD. Изменение production training code требует нового разрешённого эксперимента.

Checkpoint не содержит partial gradients. При обрыве между boundaries повторяется только следующая незакоммиченная группа из четырёх позиций, начиная с сохранённого RNG. `inflight.json` и `resume-replay.json` явно показывают discarded partial group, в том числе optimizer call до незавершённого checkpoint save. Если все 2000 updates сохранены, но оформление результата прервано, Resume step-2000 завершает export/evidence **без загрузки модели**. Без первого checkpoint продолжать нечего; нужен разбор и отдельно разрешённый новый RunId.

Run facts, per-checkpoint receipts и completed.json immutable; ошибки операций и packaging attempts отдельны. После завершения packaging error не переписывает updates, measurements, source commit или hashes. Повторная упаковка создаёт новый ZIP, сохраняя старый. Оптимизаторные checkpoints остаются локально. Diagnostics не включают raw examples, raw logs, base weights, adapter tensors, private paths или secrets; adapter ZIP содержит только LoRA и pinned references.

## Ресурсы и фиксированные пределы

Прежняя admission policy: desktop RTX3060 12GB, capability 8.6, CUDA runtime 12.6; physical/CUDA capacity ≥12000 MiB, external free ≥10800 MiB и CUDA free ≥10500 MiB до загрузки; host available ≥12 GiB. Stop: host <6 GiB, рост actual system pagefile >256 MiB, unavailable pagefile/stale GPU telemetry, CUDA free на update boundary <256 MiB. Preferred CUDA headroom=512 MiB. Измерения NVIDIA external VRAM, CUDA free, PyTorch allocated/reserved, host RAM и EnumPageFilesW pagefile сохраняются раздельно.

| Предел | Значение |
| --- | ---: |
| Prepare (включая проверку model files) | 900 s |
| Admission / runtime+hash recheck | 180 s |
| Model load и adapter/optimizer construction | 300 s |
| Одна группа 4 microbatches + update | 600 s |
| Checkpoint | 120 s |
| Package | 180 s |
| Полный run, включая паузы после Start | **86400 s / 24 h** |
| Cancellation grace перед остановкой owned Job | 5 s |
| Owner test group | 180 s |
| Свободное место перед Prepare/Start/Resume | **10 GiB** |
| Stop по свободному месту | 2 GiB |
| Максимальный checkpoint | 512 MiB |

Примерная вычислительная длительность: mean двух smoke updates (11.047 и 10.672 s) ×2000 ≈**6.03 h**, **плюс** checkpoint/I/O, подготовка и одна загрузка (в smoke 7.562 s). Это грубый ориентир из двух измерений, не обещание и не доказательство long-run stability. Не умножать время загрузки модели на 2000. Checkpoint validation после каждого update добавляет ещё не измеренные на RTX3060 расходы; V1 имеет фиксированный лимит 24h без автоматического продления.

Ожидаемый checkpoint — десятки MiB (LoRA FP32 ≈11.25 MiB + 8bit moments/metadata); резерв позволяет два checkpoint и staging до 1.5 GiB, tokens и логи. Model ≈7.5 GiB уже существует и не копируется. Частые сохранения дают десятки GiB суммарных записей на диск, а не столько одновременно занятого места. Не применять размер CPU-фикстуры как estimate реального checkpoint.

Host safety sampling=200 ms, внешний nvidia-smi=200 ms, progress≤10 s. Logs flush incrementally; каждый log/telemetry stream имеет три файла по 16 MiB. Память monitor O(1); полный список samples не накапливается. Progress показывает committed step, elapsed, last checkpoint, раздельную память и rough remaining estimate с текущим временем update+checkpoint. Windows kill-on-close Job ограничивает только собственный worker/descendants; sampler имеет отдельный owned Job. Никаких массовых Stop-Process.

## Позднейшая оценка — сейчас запрещена

1. Сначала полностью завершить V1.
2. Затем DEV и разрешённые 304 случая tuning eval.
3. Зафиксировать model/config selection.
4. Только после этого locked INTERNAL_TEST и A01–A16 для финальной оценки, без checkpoint selection и итеративного tuning.

Переиспользовать `ml/baseline/scoring.py`: JSON_VALID_RATE, SCHEMA_VALID_RATE, SEMANTIC_VALID_RATE, FULL_EXPECTED_STRUCTURE_MATCH, PRIMARY_INTENT_ACCURACY, CRITICAL_COMMITMENT_ACCURACY, AMBIGUITY_CLARIFICATION_ACCURACY, UNKNOWN_ID_RATE, UNNECESSARY_CLARIFICATION_RATE. Проверять допустимые IDs, active-offer/argument/action bindings и безопасное clarification; те же показатели срезать по всем 13 intents. Latency: mean/median/p95 nearest rank и tokens/sec including prefill. Не читать holdout примеры для выбора тренировки.

Для base-vs-adapter сравнения фиксировать один RTX3060, исходный checkpoint/tokenizer, NF4/FP16, SDPA, context/generation limits, non-thinking prompt, decoding, warmup/cache и измерение latency. RTX2060 BF16/offload timings не сравнивать с RTX3060 NF4 как эффект fine-tuning. Метрики и application integration — отдельные разрешённые gates.

Проверки владельца и границы: [gate receipt](../../docs/gates/QWEN3_4B_FULL_TRAINING_PREPARATION.md). Production Qwen/bitsandbytes/CUDA checkpoint-resume ещё не исполнялся; доказанная эквивалентность относится к deterministic CPU fixture, использующей тот же engine и checkpoint protocol. Новая RTX3060 certification campaign не требуется и не создаётся.

**STOP — FULL QWEN TRAINING AND QUALITY EVALUATION NOT STARTED.**
