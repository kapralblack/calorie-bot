-- Инициализация базы данных для телеграм-бота подсчета калорий
-- Этот файл выполняется при первом запуске PostgreSQL контейнера

-- Создание пользователя для бота (если не существует)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'bot_user') THEN

      CREATE ROLE bot_user LOGIN PASSWORD 'bot_password';
   END IF;
END
$do$;

-- Предоставляем права на базу данных
GRANT ALL PRIVILEGES ON DATABASE calorie_bot TO bot_user;

-- Подключаемся к базе данных
\c calorie_bot;

-- Предоставляем права на схему public
GRANT ALL ON SCHEMA public TO bot_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bot_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bot_user;

-- Устанавливаем права по умолчанию для будущих таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO bot_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO bot_user;
