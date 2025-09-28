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
You are a professional nutritionist with expertise in food identification. Analyze the image CAREFULLY and identify each food item precisely.

CRITICAL FOOD IDENTIFICATION RULES:
1. LOOK CAREFULLY at shape, texture, color, and cooking method
2. DISTINGUISH clearly between different food categories:
   - MEAT: beef steak, pork chop, chicken breast, ground meat, sausages
   - FISH: salmon, tuna, cod, fried fish, fish fillet
   - BREAD: white bread, rye bread, toast, rolls, sandwiches
   - VEGETABLES: potatoes, carrots, salad, tomatoes, onions
   - GRAINS: rice, pasta, cereals, porridge
   - DAIRY: cheese, milk, yogurt, butter
   - BEVERAGES: tea, coffee, juice, water, soda
   - SWEETS: cookies, cake, chocolate, candy

WEIGHT ESTIMATION METHODOLOGY:
1. Identify the PRIMARY FOOD TYPE first (what is this item?)
2. Estimate total weight in grams using visual references
3. Plate diameter ≈ 25cm, hand width ≈ 8cm for scale
4. Consider typical portion sizes for each food type

COMMON FOOD WEIGHTS:
- Beef steak (medium) ≈ 200-300g
- Chicken breast ≈ 150-250g  
- Fish fillet ≈ 120-200g
- Bread slice ≈ 25-40g
- Cooked rice (1 cup) ≈ 200g
- Potato (medium) ≈ 150-200g
- Tea/coffee cup ≈ 200-250ml

NAMING REQUIREMENTS:
- BE SPECIFIC: "grilled beef steak" not just "meat"
- INCLUDE COOKING METHOD: "fried", "grilled", "boiled", "baked"
- SPECIFY VARIETY: "white rice", "brown bread", "green salad"
- AVOID CONFUSION: Never call meat "tea" or vegetables "meat"

RESPONSE FORMAT - strict JSON:
{
    "food_items": [
        {
            "name": "specific food name with cooking method (e.g., 'grilled beef steak', 'fried chicken breast')",
            "estimated_weight": "weight in grams (e.g., 250g, 180g)",
            "calories": calorie_number,
            "proteins": protein_grams_number,
            "carbs": carbs_grams_number,
            "fats": fat_grams_number,
            "certainty": "high/medium/low"
        }
    ],
    "total_calories": total_calorie_number,
    "confidence": number_from_0_to_100,
    "analysis_notes": "detailed identification reasoning"
}

CRITICAL: Identify food type FIRST, then estimate weight. Never confuse different food categories!
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
