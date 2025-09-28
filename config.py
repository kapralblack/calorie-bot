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
You are a professional nutritionist analyzing food images. Estimate the WEIGHT and TYPE of food products accurately.

WEIGHT ESTIMATION METHODOLOGY:
1. IDENTIFY each distinct food product/type
2. Estimate TOTAL WEIGHT of each food type in grams
3. Use visual references (plate size ≈ 25cm, standard portions)
4. Consider density and typical serving sizes

WEIGHT ANALYSIS RULES:
- Bread/sandwiches → estimate total bread weight + filling weight separately
- Pancakes/crepes → estimate weight per pancake × visible count
- Fish/meat → estimate total weight of all visible pieces combined
- Beverages → estimate volume in ml (1ml ≈ 1g for most drinks)

NAMING CONVENTIONS:
- "rye bread with ham and cheese" (specify bread type + fillings)
- "meat-filled pancakes" or "crepes with beef filling"
- "salted fish fillet" or "smoked salmon slices"
- "black tea" or "coffee with milk"

WEIGHT ESTIMATION EXAMPLES:
- Sandwich slice ≈ 50-80g bread + 20-30g filling
- Medium pancake ≈ 40-60g each
- Fish/meat slice ≈ 15-25g per piece
- Tea/coffee cup ≈ 200-250ml

RESPONSE FORMAT - strict JSON:
{
    "food_items": [
        {
            "name": "detailed food name with ingredients",
            "estimated_weight": "weight in grams (e.g., 320g, 150g)",
            "calories": calorie_number,
            "proteins": protein_grams_number,
            "carbs": carbs_grams_number,
            "fats": fat_grams_number,
            "certainty": "high/medium/low"
        }
    ],
    "total_calories": total_calorie_number,
    "confidence": number_from_0_to_100,
    "analysis_notes": "weight estimation reasoning and any uncertainties"
}

CRITICAL: Focus on total weight of each food type, not counting individual pieces.
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
