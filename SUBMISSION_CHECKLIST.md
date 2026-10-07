# Финальный чек-лист SplitUZ

## Перед показом

- [ ] Docker Desktop показывает `Engine running`.
- [ ] Выполнено `docker compose up --build -d`.
- [ ] `docker compose ps` показывает `healthy` для `db` и `app`.
- [ ] `http://localhost:8000` открывается.
- [ ] `natija/balanslar.csv` существует и имеет заголовки `group_id,member_id,net_balans`.

## Пять обязательных артефактов

- [x] Работающий код — Docker Compose.
- [x] `README.md` — запуск и архитектура.
- [x] `DECISIONS.md` — алгоритмы, Big-O, edge cases, patterns.
- [x] ERD — `docs/ERD.png`, `docs/ERD.md`, `docs/schema.sql`.
- [x] Автотесты — `tests/`.

## Live demo

- [ ] Выбор группы и участника.
- [ ] Net-баланс и `sum = 0`.
- [ ] Оптимизированные переводы.
- [ ] Добавление расхода.
- [ ] RU/UZ.
- [ ] Demo QR.
- [ ] Экспорт CSV.

## Hidden dataset

1. Заменить ровно пять CSV в `dataset/`.
2. Не переносить старую папку `_javob_kaliti` в пакет сдачи.
3. Выполнить `docker compose up --build -d`.
4. Проверить UI и скачать новый `balanslar.csv`.

