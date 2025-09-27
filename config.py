"""
Конфигурация для телеграм-бота подсчета калорий
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")

# OpenAI API Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не установлен в переменных окружения")

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///calorie_bot.db')

# Bot Configuration
BOT_NAME = os.getenv('BOT_NAME', 'Калории Бот 🍎')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID', '')

# Server Configuration (для деплоя)
PORT = int(os.getenv('PORT', 8000))
HOST = os.getenv('HOST', '0.0.0.0')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')

# AI Configuration
AI_MODEL = "gpt-4o"
MAX_TOKENS = 1000

# Настройки анализа калорий
CALORIE_PROMPT = """
Внимательно проанализируй это изображение еды и предоставь максимально точную информацию о калориях.

ВАЖНЫЕ ПРАВИЛА:
1. ТОЧНО подсчитай количество каждого предмета - считай только то, что ЧЕТКО видно
2. НЕ додумывай и НЕ предполагай наличие скрытых предметов  
3. Если сомневаешься в количестве - укажи это в portion_size
4. Оценивай размер порций реалистично (стандартные размеры)
5. Учитывай толщину, плотность и ингредиенты блюд

ФОРМАТ ОТВЕТА - строго JSON:
{
    "food_items": [
        {
            "name": "точное название блюда/продукта",
            "portion_size": "конкретное количество с единицами (например: 4 штуки, 1 средняя тарелка, 200мл)",
            "calories": количество_калорий_число,
            "proteins": граммы_белка_число,
            "carbs": граммы_углеводов_число,
            "fats": граммы_жиров_число,
            "certainty": "высокая/средняя/низкая - насколько уверен в этом предмете"
        }
    ],
    "total_calories": общее_количество_калорий_число,
    "confidence": число_от_0_до_100,
    "analysis_notes": "краткие заметки о том, что было сложно определить или вызвало сомнения"
}

Если на изображении нет еды, верни confidence: 0 и объясни что видишь в analysis_notes.
"""

# Эмодзи для интерфейса
EMOJIS = {
    'food': '🍽️',
    'stats': '📊',
    'calendar': '📅',
    'fire': '🔥',
    'scales': '⚖️',
    'chart': '📈',
    'settings': '⚙️',
    'help': '❓',
    'back': '⬅️',
    'checkmark': '✅',
    'warning': '⚠️',
    'error': '❌',
    'apple': '🍎',
    'water': '💧',
    'muscle': '💪'
}
