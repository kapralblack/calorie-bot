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
You are a professional nutritionist analyzing food images. Count items PRECISELY and be EXTREMELY accurate.

COUNTING METHODOLOGY:
1. LOOK CAREFULLY at each distinct food item
2. Count slices, pieces, portions individually 
3. If food is cut/sliced, count VISIBLE pieces
4. Group similar items together (e.g., "4 sandwich pieces" not "4 different sandwiches")

VISUAL ANALYSIS RULES:
- Sliced sandwiches/bread → count each visible slice/piece
- Pancakes/crepes → count each individual pancake
- Fish/meat pieces → count each separate piece  
- Beverages → count containers (cups, glasses)

NAMING CONVENTIONS:
- "ham and cheese sandwiches" (not just "cheese" or just "ham")
- "meat-filled pancakes" (if you see filling)
- "sliced fish" (specify type if visible)
- "tea/coffee" (specify beverage type)

PORTION SIZE FORMAT:
- "4 pieces" (not "4 sandwiches" if they're cut pieces)
- "3 pancakes" (individual count)
- "2 slices" (for fish/meat)
- "1 cup" (for beverages)

RESPONSE FORMAT - strict JSON:
{
    "food_items": [
        {
            "name": "precise food name with main ingredients",
            "portion_size": "exact count with units (e.g., 4 pieces, 3 pancakes, 2 slices)",
            "calories": calorie_number,
            "proteins": protein_grams_number,
            "carbs": carbs_grams_number,
            "fats": fat_grams_number,
            "certainty": "high/medium/low"
        }
    ],
    "total_calories": total_calorie_number,
    "confidence": number_from_0_to_100,
    "analysis_notes": "what you identified and any uncertainties"
}

CRITICAL: Count each visible piece/slice/item separately. Be precise and consistent.
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
