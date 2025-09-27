"""
Webhook сервер для телеграм-бота (для продакшен деплоя)
"""
import asyncio
import logging
from aiohttp import web, web_request
from telegram import Update
from telegram.ext import Application
import config
from bot import CalorieBotHandlers
from database import create_tables

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class WebhookServer:
    """Веб-сервер для обработки webhook запросов от Telegram"""
    
    def __init__(self):
        self.application = None
        self.setup_bot()
    
    def setup_bot(self):
        """Настройка телеграм-бота"""
        # Создаем таблицы базы данных
        create_tables()
        logger.info("База данных инициализирована")
        
        # Создаем приложение
        self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        
        # Регистрируем обработчики
        from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters
        
        self.application.add_handler(CommandHandler("start", CalorieBotHandlers.start_command))
        self.application.add_handler(CommandHandler("help", CalorieBotHandlers.help_command))
        self.application.add_handler(CommandHandler("stats", CalorieBotHandlers.stats_handler))
        self.application.add_handler(CommandHandler("settings", CalorieBotHandlers.settings_handler))
        
        # Обработчики сообщений
        self.application.add_handler(MessageHandler(filters.PHOTO, CalorieBotHandlers.photo_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, CalorieBotHandlers.text_handler))
        
        # Обработчик inline кнопок
        self.application.add_handler(CallbackQueryHandler(CalorieBotHandlers.button_handler))
        
        logger.info(f"Бот {config.BOT_NAME} настроен для webhook режима")
    
    async def webhook_handler(self, request: web_request.Request):
        """Обработчик webhook запросов"""
        try:
            # Получаем данные из запроса
            data = await request.json()
            
            # Создаем объект Update
            update = Update.de_json(data, self.application.bot)
            
            if update:
                # Обрабатываем обновление
                await self.application.process_update(update)
                return web.Response(text="OK")
            else:
                logger.warning("Получено пустое обновление")
                return web.Response(status=400, text="Bad Request")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке webhook: {e}")
            return web.Response(status=500, text="Internal Server Error")
    
    async def health_check(self, request: web_request.Request):
        """Проверка состояния сервера"""
        return web.json_response({
            "status": "healthy",
            "bot_name": config.BOT_NAME,
            "timestamp": asyncio.get_event_loop().time()
        })
    
    async def setup_webhook(self):
        """Настройка webhook в Telegram"""
        try:
            webhook_url = f"{config.WEBHOOK_URL}/webhook"
            await self.application.bot.set_webhook(
                url=webhook_url,
                allowed_updates=["message", "callback_query"]
            )
            logger.info(f"Webhook установлен: {webhook_url}")
        except Exception as e:
            logger.error(f"Ошибка установки webhook: {e}")
    
    def create_app(self):
        """Создание web приложения"""
        app = web.Application()
        
        # Маршруты
        app.router.add_post('/webhook', self.webhook_handler)
        app.router.add_get('/health', self.health_check)
        app.router.add_get('/', self.health_check)
        
        return app

async def init_app():
    """Инициализация приложения"""
    server = WebhookServer()
    
    # Инициализируем бота
    await server.application.initialize()
    await server.application.start()
    
    # Настраиваем webhook
    if config.WEBHOOK_URL:
        await server.setup_webhook()
    
    return server.create_app()

def main():
    """Основная функция запуска сервера"""
    if not config.WEBHOOK_URL:
        logger.error("WEBHOOK_URL не установлен в переменных окружения")
        return
    
    # Создаем и запускаем сервер
    app = asyncio.get_event_loop().run_until_complete(init_app())
    
    logger.info(f"Запускаем webhook сервер на {config.HOST}:{config.PORT}")
    web.run_app(
        app,
        host=config.HOST,
        port=config.PORT,
        access_log=logger
    )

if __name__ == '__main__':
    main()
