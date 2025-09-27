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
# AI Configuration - English prompts for better understanding
CALORIE_PROMPT = """
You are a professional nutritionist. Analyze this food image with MAXIMUM CONSISTENCY and accuracy.

CRITICAL STABILITY RULES:
1. Look at the image as COMPLETE DISHES, not individual ingredients
2. Count ONLY what is clearly visible as separate items
3. Use STANDARD portion sizes for calculations
4. Be CONSISTENT in naming (e.g., always "sandwich" not "ham slices + cheese slices")
5. If you see layered food, count it as ONE item (e.g., "sandwich with ham and cheese", not separate ham and cheese)

IDENTIFICATION PRIORITY:
- Sandwiches/burgers = count as complete items
- Pancakes/crepes = count individual pieces  
- Fish/meat = count individual pieces
- Drinks = count containers

RESPONSE FORMAT - strict JSON:
{
    "food_items": [
        {
            "name": "exact food item name (use complete dish names like 'ham and cheese sandwich')",
            "portion_size": "specific amount (e.g., 4 sandwiches, 3 pancakes)",
            "calories": calorie_number,
            "proteins": protein_grams_number,
            "carbs": carbs_grams_number,
            "fats": fat_grams_number,
            "certainty": "high/medium/low"
        }
    ],
    "total_calories": total_calorie_number,
    "confidence": number_from_0_to_100,
    "analysis_notes": "brief notes about what you identified and your confidence level"
}

IMPORTANT: Be consistent in your analysis - the same image should always produce the same result.
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
