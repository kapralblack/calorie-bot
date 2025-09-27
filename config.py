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
Carefully analyze this food image and provide accurate calorie information.

CRITICAL RULES:
1. COUNT EXACTLY what you see - only clearly visible items
2. DO NOT guess or assume hidden food items
3. If uncertain about quantity, mention it in portion_size
4. Use realistic portion sizes (standard serving sizes)
5. Consider thickness, density, and ingredients of dishes

RESPONSE FORMAT - strict JSON:
{
    "food_items": [
        {
            "name": "exact food item name",
            "portion_size": "specific amount with units (e.g., 4 pieces, 1 medium plate, 200ml)",
            "calories": calorie_number,
            "proteins": protein_grams_number,
            "carbs": carbs_grams_number,
            "fats": fat_grams_number,
            "certainty": "high/medium/low - how confident you are about this item"
        }
    ],
    "total_calories": total_calorie_number,
    "confidence": number_from_0_to_100,
    "analysis_notes": "brief notes about what was difficult to determine or caused uncertainty"
}

If no food is visible, return confidence: 0 and explain what you see in analysis_notes.
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
