# РАЗВЕДКА — локальный поиск лидов по картам

Установка: `run.bat` создаёт .venv, ставит зависимости из requirements.txt и скачивает Chromium.
Запуск: двойной клик по `run.bat`. Приложение откроет http://127.0.0.1:8000 в браузере.
Данные: `data/rozvedka.db` (SQLite WAL), `data/browser_profile/` (профиль Chrome), копии БД в `data/backups/` (последние 5).
Отладка: `debug/capture/<источник>/<время>/` — HTML, скриншоты и JSON-ответы; логи в `logs/`.
Тесты: `.venv\Scripts\python.exe -m pytest -q`; с покрытием: `-m pytest -q --cov=app --cov-report=term`.
Live-тесты (реальные сайты, только Саратов): `.venv\Scripts\python.exe -m pytest -m live -q`.
EPA: источники Google, Яндекс, 2ГИС; обогащение сайтов; промпты для чатботов без вызовов LLM.
Отправку сообщений пользователь выполняет вручную в окне мессенджера.
Настройки, фильтры, шаблоны и состояние заданий сохраняются в локальной БД.
Стек: FastAPI + Uvicorn, Jinja2, HTMX, Alpine.js, SQLAlchemy 2, SQLite WAL, Playwright sync, pydantic v2.
Только локальный запуск: сервер слушает 127.0.0.1, облачные API и ключи не используются.
