# Передача владельцем

Внешний `rtx3060-12gb-gate-bundle/01-materialize-rtx3060-12gb-gate.ps1` устарел. Не запускать повторно: исправленные исходники находятся непосредственно в `tools/windows-rtx3060-12gb-1536/` на `main` авторитетного origin.

Отправить другу:

1. `.tmp/rtx3060-12gb-targeted-1536-smoke/transfer/Qwen3-4B.tar`
2. `.tmp/rtx3060-12gb-targeted-1536-smoke/transfer/Qwen3-4B.tar.sha256`
3. `tools/windows-rtx3060-12gb-1536/START_HERE_RU.md`
4. Ссылку для клонирования: `https://github.com/AiratBastanov/TalkNFace.git`.

Исторический TAR на рабочем столе отсутствовал. По явному запросу владельца создан новый TAR размером **8 060 907 520 байт**, SHA256 **D69F99B94DD0E5346F5882F6ED327BEE925D060659648FB75877C1C0D5FCE09A**. Он содержит только десять файлов исходного model-lock. Проверены исходные файлы, payload TAR и импорт в отдельный staging; модель не загружалась для вычислений. Архив и веса игнорируются Git.

Получить обратно только `RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip`. Из корня checkout той же ревизии выполнить:

```powershell
python -B .\tools\windows-rtx3060-12gb-1536\verify_result.py .\handoff-results\RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip
```

Verifier использует stdlib и не требует ML-окружения или модели. Выход 0 означает проверенный PASS/PASS_TIGHT_MEMORY; выход 2 — обучение не сертифицировано. `--archive-only` проверяет только целостность ZIP. При другой ревизии checkout сверка источников закономерно не пройдёт; не обходить её подменой commit/hash.

Owner verdict `WINDOWS_RTX3060_12GB_HANDOFF_CORRECTION_PASS` относится к исправлению и проверке handoff. У владельца RTX2060 6 ГБ: RTX3060 hardware smoke — **NOT RUN**, полное обучение — **NOT STARTED**, G3/application integration — **NOT STARTED**. Реальное измерение всех 8000 TRAIN tokenizer/compiler и файловые проверки не являются обучением или оценкой качества.
