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

# Логирование информации о базе данных
def log_database_info():
    """Логирование информации о подключении к базе данных"""
    import logging
    logger = logging.getLogger(__name__)
    
    if DATABASE_URL.startswith('postgresql'):
        # Скрываем пароль в логах для безопасности
        safe_url = DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL
        logger.info(f"🐘 Используется PostgreSQL: {safe_url}")
        logger.info("✅ Данные пользователей будут сохраняться между перезапусками")
    elif DATABASE_URL.startswith('sqlite'):
        logger.warning("⚠️ Используется SQLite - данные будут сбрасываться при деплое!")
        logger.warning("💡 Настройте PostgreSQL в Railway для постоянного хранения")
    else:
        logger.info(f"🔍 Используется база данных: {DATABASE_URL[:20]}...")

# Bot Configuration
BOT_NAME = os.getenv('BOT_NAME', 'Калории Бот 🍎')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID', '')

# FatSecret API Configuration
FATSECRET_CONSUMER_KEY = os.getenv('FATSECRET_CONSUMER_KEY', '')
FATSECRET_CONSUMER_SECRET = os.getenv('FATSECRET_CONSUMER_SECRET', '')

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
2. EXAMINE COMPLEX DISHES: Look for multiple layers, fillings, and hidden ingredients
3. DISTINGUISH clearly between different food categories:
   - MEAT: beef steak, pork chop, chicken breast, ground meat, sausages
   - FISH: salmon, tuna, cod, fried fish, fish fillet  
   - BREAD: white bread, rye bread, toast, rolls, sandwiches
   - VEGETABLES: potatoes, carrots, salad, tomatoes, onions
   - GRAINS: rice, pasta, cereals, porridge
   - DAIRY: cheese, milk, yogurt, butter
   - BEVERAGES: tea, coffee, juice, water, soda
   - SWEETS: cookies, cake, chocolate, candy

COMPLEX DISH ANALYSIS:
For layered/composite dishes (casseroles, pies, gratins, stuffed items):
1. IDENTIFY ALL VISIBLE COMPONENTS: Don't reduce complex dishes to single ingredients
2. ANALYZE LAYERS: Top layer (cheese, crust), middle layer (filling), bottom layer (base)
3. RECOGNIZE MIXED INGREDIENTS: In casseroles and pies, identify meat, vegetables, sauce, cheese
4. ESTIMATE PROPORTIONS: If you see cheese on top of meat filling, include BOTH components
5. COMMON COMPLEX DISHES:
   - Meat casserole = ground meat + vegetables + cheese topping
   - Quiche/pie = egg filling + vegetables/meat + pastry crust
   - Gratin = vegetables + cream sauce + cheese topping
   - Stuffed items = main item + filling ingredients

NEVER simplify complex dishes to just one ingredient!

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

COMPLEX DISH WEIGHTS:
- Meat casserole portion ≈ 300-500g (meat 200g + vegetables 100g + cheese 50g + sauce 50g)
- Quiche slice ≈ 150-250g (pastry 50g + egg filling 100g + cheese/meat 50g)  
- Gratin portion ≈ 200-350g (vegetables 200g + cream sauce 100g + cheese 50g)
- Stuffed pepper ≈ 200-300g (pepper 100g + meat/rice filling 150g)
- Pie slice ≈ 150-300g (crust 50g + filling varies 100-250g)

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

CRITICAL REQUIREMENTS:
1. Identify food type FIRST, then estimate weight
2. Never confuse different food categories!  
3. For complex/layered dishes: LIST ALL VISIBLE COMPONENTS separately
4. Example: If you see cheese on top of meat filling, report BOTH "baked cheese topping 50g" AND "ground meat filling 200g"
5. NEVER reduce complex dishes to just one ingredient (e.g., meat casserole ≠ just "cheese")

ANALYSIS EXAMPLE FOR COMPLEX DISHES:
- Visible: Golden cheese layer on top, meat/vegetable filling visible in cross-section
- Report: ["baked cheese topping", "ground meat with vegetables", "pastry base"] 
- NOT just: ["cheese"]
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
