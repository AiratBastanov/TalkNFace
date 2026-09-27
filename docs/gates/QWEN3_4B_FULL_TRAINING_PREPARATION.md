# QWEN3_4B_FULL_TRAINING_PREPARATION

**Verdict: `QWEN3_4B_FULL_TRAINING_PREPARATION_PASS`.** Реализован, проверен и подготовлен к передаче отдельный Windows workflow первого полного TRAIN pass. Это verdict инфраструктуры: **полное обучение Qwen, inference и оценка качества не запускались**.

Implementation commit: `deccdc32cc7bcb69c78d041e6edfef8fc52c6e6c`. [Русская инструкция другу с командами](../../tools/windows-rtx3060-full-training/README_RU.md), [entry point](../../tools/windows-rtx3060-full-training/RUN-FULL-TRAINING.ps1), [замороженный V1 config](../../tools/windows-rtx3060-full-training/candidate-v1.json), [машиночитаемый receipt](evidence/QWEN3_4B_FULL_TRAINING_PREPARATION.json).

## Историческое принятие до изменения source

Начальный checkout: чистый `main`, HEAD `e3de4db26a6c4dad25dc51a6b321ff2b434d0e00`, fetch/push origin `https://github.com/AiratBastanov/TalkNFace.git`, ahead/behind 0/0. Поэтому изолированный checkout для первоначального принятия не требовался.

Путь из запроса `Alag.tmp\...` отсутствовал; точный файл найден в **`Alag\.tmp\rtx3060-final-acceptance\final.zip`**, выбран по полному SHA256 и размеру, не по похожему имени:

`2D90867E8BE4960C1878EFFA12C3DDC20ACBC1C4609AE4C952F33BF0B8E220ED`, **65320 bytes**.

Фактически выполнено до создания новых tracked files:

```powershell
python -B tools/windows-rtx3060-12gb-1536/verify_result.py .tmp/rtx3060-final-acceptance/final.zip
```

Exit=0; `archive_integrity=PASS`, `training_gate=RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_SMOKE_PASS`, `certified_training_pass=true`, `failed_checks=[]`. Verifier version: recorded packaging commit плюс hashes verifier и его зависимостей в [accepted-baseline.json](../../tools/windows-rtx3060-full-training/accepted-baseline.json). Historical training source: `1c270adba77545720fa33bcee0e24f7d6f46e55d`. Его конфигурация, source/model/tokenizer/data/runtime pins сохранены отдельно от V1.

Приняты 8000 измеренных TRAIN rows, max=1421 при limit=1536, без truncation; 8 microbatches / 2 optimizer updates; CUDA free на boundaries 3933 / 1160.6484375 MiB, внешний минимум 1002 MiB; изменены 144/144 adapter tensors; fresh-process reload/finite logits и все 27 outcome checks прошли. Quality evaluation и full training в этом ZIP не выполнялись.

Старые smoke files/ZIP/allowlist не изменены; новые training files не включаются в историческую область сертификации. Новая система хранит typed identities: `accepted_historical_smoke`, `full_training_source`, `packaging_verifier`. Будущий run зафиксирует фактический commit при Prepare; поздний packaging HEAD не заменяет его. Для повторной **архивной** проверки после продвижения HEAD предназначен `accept_historical.py --checkout <отдельный чистый checkout e3de4db...>`; reset/rebase существующего checkout не применяется.

## Замороженная первая кандидатура

Один детерминированный shuffled TRAIN epoch: **8000 rows / 8000 microbatches / 2000 успешных updates**, accumulation=4, batch=1. Data seed и model seed=20260917. Python permutation и cursor сохраняются. Полная tokenization и completion masks используют принятые `compile_sft.py`, `tokenize_record`, `verify_labels` и установленный TRL collator. Модель — интерпретатор существующего структурного контракта; никаких правок приложения, G3, utility/acceptance/scoring, сценариев, корпуса или split assignment.

Исходный `Qwen/Qwen3-4B@1cfa9a7208912126459214e8b04321603b3df60c`; новый LoRA, без чтения smoke adapter. NF4/double quant, FP16, explicit CUDA:0, SDPA, q/v only r8/alpha16/dropout.05/bias none, 2949120 trainable parameters; explicit pinned-host activation offload и reentrant=True как в smoke. BF16, TF32, auto device map, CPU weight offload, другой allocator/attention/optimizer не включаются.

LR=.0002; фактический bitsandbytes AdamW weight_decay=.01 задан явно, betas=.9/.999, eps=1e-8, min_8bit_size=4096, paged=true, optim_bits=8. В smoke weight_decay пришёл из default установленного optimizer, а не из неиспользованного Trainer grouping. Full-only scheduler: constant, warmup=0. Checkpoint после каждого update — также full-only setting. Loss — среднее четырёх средних completion-token losses; итоговая агрегация по committed records. Nonfinite loss/gradients или AMP skip дают failure без ложного продвижения cursor и без автоматического retry.

SHA256 candidate config: `41b3bd010d62d53435b988086984d5e169c2c226746c64775281d60aaa5bd85d`.

## Checkpoint и эксплуатация

Prepare/Status/Package/DryRun не исполняют Qwen; без Action показывается Help. Start требует отдельный RunId и matching AuthorizeNewRun. Resume отдельно требует newest verified checkpoint этого run. OS lock защищает run, отдельный GPU operation lock исключает одновременный запуск двух run. PowerShell 5.1, literal/quoted paths, Cyrillic/spaces и native exit codes проверены.

Checkpoint step-0000 и каждый последующий содержат adapter/config, optimizer/scheduler/scaler, Python/NumPy/Torch/CUDA RNG, epoch/step/order/cursor, полный run/pin identity и integrity manifest. Staging, fsync, CPU deserialize/safetensors validation и hashes предшествуют atomic rename/LATEST. Сохраняются два verified checkpoints. Incomplete, corrupted, truncated, чужой или stale checkpoint не выбирается. Полная база не копируется/сериализуется. Partial accumulation group явно отмечается; resume восстанавливает RNG и повторяет только незакоммиченную группу. Offline finalization после step-2000 не исполняет модель.

Runtime, checkpoints, final adapter и result ZIP имеют отдельные пути под новыми ignored roots. При packaging failure завершённые run facts остаются byte-identical. Diagnostics и deployable adapter выдаются раздельно; optimizer checkpoints локальны, base weights/raw examples/secrets не пакуются. Поздние packaging versions и существующие архивы покрыты fixture regression. Archive-integrity PASS не является model-quality PASS.

## Фиксированные ресурсы и длительность

Повторно используется принятая RTX3060 policy: desktop 12GB/capability8.6/CUDA12.6; external free≥10800 MiB, CUDA free≥10500 MiB, available RAM≥12GiB перед загрузкой. Stop при RAM<6GiB, pagefile growth>256MiB, утрате required telemetry или boundary CUDA free<256MiB. External VRAM, CUDA free, Torch allocated/reserved, RAM и actual EnumPageFilesW pagefile учитываются отдельно.

Prepare=900s, admission=180s, load=300s, group/update=600s, checkpoint=120s, packaging=180s; run wall-clock=**24h с учётом пауз**, cancel grace=5s. Продления и автоматические retries отсутствуют. Windows Job закрывает только owned worker/descendants; nvidia sampler отдельно owned. Sampling=200ms, progress≤10s, flushing incremental, telemetry memory O(1), rotation: три файла по 16MiB на stream.

Свободное место: **10GiB**; stop при <2GiB. Checkpoint ceiling=512MiB; два verified плюс staging≤1.5GiB при штатной смене. Подготовленный token JSONL фактически **75 066 982 bytes**; модель уже существует и не копируется. Ожидаемые checkpoints — десятки MiB, но actual production size пока не измерен. Частое сохранение означает десятки GiB суммарных disk writes.

Грубый ориентир: (11.047+10.672)/2 ×2000 =21719s ≈**6.03h вычислений плюс checkpoint/I/O**. Model load 7.562s учтён один раз. Два smoke updates не доказывают многочасовую устойчивость; ни оценка длительности, ни новый workflow не сертифицируют полный hardware run.

## Проверки владельца

Финальная серия: **20 focused tests PASS** — controls 9 (3.219s), checkpoint/resume 6 (5.812s), result pipeline 5 (5.829s). Каждый group ограничен watchdog=180s. Плюс реальный tokenizer/compiler/collator pass — 58.890s, также под 180s watchdog.

Реально проверены: финальный исторический ZIP строгим verifier; все 8000 TRAIN строк; min/max=663/1421; 8000 prompt/complete JSON/EOS masks реальным TRL; negative prompt/EOS controls; реальный Windows PowerShell 5.1 с Cyrillic/spaces и native exit=37; OS locks, bounded process tree, сохранение unrelated process и log rotation. Deterministic order SHA256=`28039d85dbc95113ba6c022d2285ad7d27e25fd8fb59396120255b481f888eb6`.

CPU fixture: реальный Torch AdamW/GradScaler/dropout/RNG, тот же engine и checkpoint protocol; continuous vs interrupted/resumed имеют одинаковые weights, losses, optimizer/scheduler/scaler и RNG states. Проверены corrupt/truncated/model/data/config/runtime/run mismatches, incomplete save, stale resume, explicit authorization, deadline и AMP skip. Настоящий путь runtime→immutable facts→collect→ZIP→independent verifier проверен вместе с ошибкой второй упаковки, повтором, поздней packaging identity и byte-identical completed evidence.

Обнаружены и исправлены до финальной серии: nested JSON key sorting менял prompt и max length; CPU optimizer health check первоначально инициализировал CUDA context. Новый projection сохраняет исходный порядок; owner fixture subprocesses явно скрывают GPU. Qwen ни разу не загружался, CUDA training не выполнялся; финальный tokenizer check подтвердил CUDA_initialized=false.

**Production Qwen/NF4/8bit optimizer serialization/resume и многократные saves на RTX3060 в этом gate не исполнялись.** CPU equivalence не является hardware equivalence. Не выполнялись новая smoke campaign, inference, DEV/tuning eval/INTERNAL_TEST/A01–A16 или чтение holdout examples для training design. Пакеты не устанавливались.

## Следующая граница и delivery

Предпосылка будущего запуска: отдельное разрешение владельца на новый V1 run и успешный Prepare/resource admission в уже проверенной среде друга. После полного V1: DEV + permitted 304-case tuning eval; затем freeze model/config selection; только после freeze — locked INTERNAL_TEST и A01–A16. Сохранены определения метрик parsing/schema/semantics, bindings, critical commitments, safe clarification, per-intent и latency из `ml/baseline/scoring.py`; список и порядок приведены в русской инструкции.

Base-vs-adapter quality/latency требует контролируемых одинаковых GPU/NF4/FP16/SDPA/tokenizer/prompt/decoding/warmup/cache conditions. Сравнение RTX2060 BF16/offload с RTX3060 NF4 не приписывается fine-tuning. Улучшение TRAIN loss не разрешает G3.

Git delivery: обычные commits на authoritative origin/main, без reset/clean/stash/restore/rebase/amend/force-push; staged только 21 новый workflow file и два receipt. Финальный receipt commit определяется `git log -1 --format=%H -- docs/gates/QWEN3_4B_FULL_TRAINING_PREPARATION.md`; конечные clean status / remote SHA / ahead-behind 0/0 проверяются после push и сообщаются в handoff. Все ранее tracked paths остаются без изменений; ZIP/weights/venv/checkpoints не входят в Git.

`REAL_APPLICATION_SMOKE = NOT_APPLICABLE_WITH_REASON`: training infrastructure only; application behavior unchanged.

**STOP — FULL QWEN TRAINING AND QUALITY EVALUATION NOT STARTED.**
