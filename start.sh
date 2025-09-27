#!/bin/bash

# Скрипт для запуска телеграм-бота подсчета калорий

set -e

echo "🍎 Запуск телеграм-бота подсчета калорий..."

# Проверяем существование .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    echo "📝 Создайте файл .env на основе config.py с вашими настройками:"
    echo ""
    echo "TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here"
    echo "OPENAI_API_KEY=your_openai_api_key_here"
    echo "DATABASE_URL=sqlite:///calorie_bot.db"
    echo "BOT_NAME=Калории Бот 🍎"
    echo "ADMIN_USER_ID=your_telegram_user_id_here"
    echo ""
    exit 1
fi

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "📦 Установите Docker для запуска бота в контейнере"
    echo "🔗 https://docs.docker.com/get-docker/"
    exit 1
fi

# Проверяем наличие Docker Compose
if ! command -v docker-compose &> /dev/null; then
    if ! docker compose version &> /dev/null; then
        echo "❌ Docker Compose не установлен!"
        echo "📦 Установите Docker Compose для запуска бота"
        exit 1
    fi
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Функция для отображения помощи
show_help() {
    echo "Использование: $0 [опция]"
    echo ""
    echo "Опции:"
    echo "  start         Запуск бота в режиме polling (по умолчанию)"
    echo "  webhook       Запуск бота в режиме webhook для продакшена"
    echo "  dev           Запуск бота в режиме разработки"
    echo "  stop          Остановка всех контейнеров"
    echo "  logs          Показать логи бота"
    echo "  build         Пересборка контейнеров"
    echo "  clean         Полная очистка (контейнеры, образы, данные)"
    echo "  status        Статус контейнеров"
    echo "  help          Показать эту справку"
    echo ""
}

# Создаем необходимые папки
mkdir -p data logs

case "${1:-start}" in
    "start")
        echo "🚀 Запускаем бота в режиме polling..."
        $COMPOSE_CMD up -d calorie-bot postgres
        echo "✅ Бот запущен!"
        echo "📊 Для просмотра логов: ./start.sh logs"
        ;;
    
    "webhook")
        if [ -z "$WEBHOOK_URL" ]; then
            echo "❌ Для webhook режима необходимо установить WEBHOOK_URL в .env файле"
            exit 1
        fi
        echo "🚀 Запускаем бота в режиме webhook..."
        $COMPOSE_CMD --profile webhook up -d calorie-bot-webhook postgres
        echo "✅ Бот запущен в webhook режиме!"
        echo "🌐 Webhook URL: $WEBHOOK_URL"
        ;;
    
    "dev")
        echo "🔧 Запускаем бота в режиме разработки..."
        python -m pip install -r requirements.txt
        python bot.py
        ;;
    
    "stop")
        echo "🛑 Останавливаем все контейнеры..."
        $COMPOSE_CMD down
        echo "✅ Все контейнеры остановлены"
        ;;
    
    "logs")
        echo "📄 Логи бота:"
        $COMPOSE_CMD logs -f calorie-bot calorie-bot-webhook
        ;;
    
    "build")
        echo "🔨 Пересборка контейнеров..."
        $COMPOSE_CMD build --no-cache
        echo "✅ Контейнеры пересобраны"
        ;;
    
    "clean")
        echo "🧹 Полная очистка..."
        read -p "⚠️  Это удалит ВСЕ данные бота! Продолжить? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            $COMPOSE_CMD down -v --remove-orphans
            docker system prune -af
            rm -rf data/* logs/*
            echo "✅ Очистка завершена"
        else
            echo "❌ Очистка отменена"
        fi
        ;;
    
    "status")
        echo "📊 Статус контейнеров:"
        $COMPOSE_CMD ps
        ;;
    
    "help")
        show_help
        ;;
    
    *)
        echo "❌ Неизвестная команда: $1"
        show_help
        exit 1
        ;;
esac
