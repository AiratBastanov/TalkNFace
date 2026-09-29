# Как развернуть и запустить TalkNFace

Инструкция для организаторов и жюри. Публичного сайта нет: прототип работает на вашем компьютере. Ключ API, CUDA и модель не нужны.

## Что понадобится

- Windows 10 или 11, 64-bit
- Windows PowerShell
- Google Chrome (для показа в браузере)
- Интернет **только на первую подготовку** (скачивание Node.js 24.21.0 и пакетов npm)
- Около 2 ГБ свободного места

Python, Docker, Visual Studio и права администратора Windows не требуются.

## 1. Получить исходники

Клонируйте эту ветку в папку без кириллицы в коротком пути, если возможно:

```powershell
git clone --single-branch --branch docs/organizer-presentation-01 https://github.com/AiratBastanov/TalkNFace.git TalkNFace
Set-Location TalkNFace
```

Либо распакуйте ZIP репозитория и откройте PowerShell в корне, где лежит `package.json` и `scripts\windows-demo.ps1`.

## 2. Подготовить среду

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Prepare
```

Скрипт дважды попросит **придумать пароль администратора** (12–256 символов). Общего пароля в репозитории нет: задайте свой и запомните его. Сохраняется только хеш, не сам пароль.

Первый Prepare скачивает закреплённый Node.js и ставит зависимости. Повторный Prepare можно запускать, если шаг прервался.

## 3. Запустить сервер

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Start -Port 3100
```

Подождите несколько секунд, пока в консоли не появится готовность.

## 4. Открыть в браузере

Пишите именно `127.0.0.1`, не `localhost`.

| Кто | Адрес |
| --- | --- |
| Администратор | http://127.0.0.1:3100/admin |
| Игрок | http://127.0.0.1:3100/ |

Войдите в `/admin` паролем из шага 2. Игроку регистрация не нужна.

Дальше по сценарию 3–5 минут: [DEMO_GUIDE_RU.md](DEMO_GUIDE_RU.md) — настроить шесть полей, опубликовать, сыграть, открыть разбор.

## 5. Остановить

После показа, **отдельной** командой:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Stop
```

Данные попыток сохраняются. Следующий Start на том же порту их не стирает.

Проверить, запущен ли сервер: `-Status`.

## Если что-то пошло не так

- **Порт занят.** Укажите другой, например `-Port 3101`, и откройте тот же порт в браузере.
- **Страница не открывается.** Убедитесь, что использовали `127.0.0.1`, а не `localhost`, и что Start завершился без ошибки.
- **Нет сети на Prepare.** Разрешите доступ к nodejs.org, registry.npmjs.org и github.com, затем повторите Prepare.
- **Нужна справка скрипта.** `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-demo.ps1 -Help`

Каталоги `ml/`, `tools/windows-rtx*` и обучение модели к этому запуску не относятся — их запускать не нужно.

Подробности runtime — в [корневом README](../README.md). Обзор продукта — [submission/PRODUCT_OVERVIEW_RU.md](submission/PRODUCT_OVERVIEW_RU.md).
