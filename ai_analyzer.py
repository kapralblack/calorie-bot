"""
AI анализатор для подсчета калорий по фотографиям еды
"""
import openai
import json
import base64
from io import BytesIO
from PIL import Image
import config
import logging
from food_database import food_database
import hashlib
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка OpenAI
openai.api_key = config.OPENAI_API_KEY

# Расширенный словарь переводов еды
FOOD_TRANSLATIONS = {
    # Бутерброды и сэндвичи
    'ham and cheese sandwiches': 'бутерброды с ветчиной и сыром',
    'ham and cheese sandwich': 'бутерброд с ветчиной и сыром', 
    'slices of ham with cheese strips': 'бутерброды с колбасой и сыром',
    'ham with cheese strips': 'бутерброды с колбасой и сыром',
    'sandwiches with ham and cheese': 'бутерброды с ветчиной и сыром',
    'cheese and ham sandwiches': 'бутерброды с сыром и ветчиной',
    'sandwiches': 'бутерброды',
    'sandwich pieces': 'кусочки бутербродов',
    'ham sandwich': 'бутерброд с ветчиной',
    'cheese sandwich': 'бутерброд с сыром',
    
    # Блины и оладьи
    'meat-filled pancakes': 'блины с мясом',
    'pancakes with meat': 'блины с мясом',
    'crepes with meat': 'блины с мясом', 
    'crepes': 'блины',
    'pancakes': 'блины',
    'meat pancakes': 'блины с мясом',
    'stuffed pancakes': 'блины с начинкой',
    
    # Рыба
    'sliced salmon': 'кусочки лосося',
    'salmon slices': 'кусочки лосося',
    'fish slices': 'кусочки рыбы',
    'sliced fish': 'кусочки рыбы',
    'salmon': 'лосось',
    'lightly salted fish': 'рыба слабой соли',
    'salted fish': 'соленая рыба',
    'smoked salmon': 'копченый лосось',
    
    # Напитки
    'cup of tea': 'чашка чая',
    'tea cup': 'чашка чая',
    'tea': 'чай',
    'black tea': 'черный чай',
    'green tea': 'зеленый чай',
    'herbal tea': 'травяной чай',
    'coffee': 'кофе',
    'cup of coffee': 'чашка кофе',
    
    # Мясные блюда
    'beef steak': 'говяжий стейк',
    'grilled beef steak': 'стейк говяжий на гриле',
    'fried beef steak': 'жареный говяжий стейк',
    'pork steak': 'свиной стейк',
    'chicken breast': 'куриная грудка',
    'grilled chicken': 'курица гриль',
    'fried chicken': 'жареная курица',
    'roast beef': 'ростбиф',
    'beef': 'говядина',
    'pork': 'свинина',
    'chicken': 'курица',
    'steak': 'стейк',
    'grilled meat': 'мясо на гриле',
    'fried meat': 'жареное мясо',
    'roasted meat': 'запеченное мясо',
    'barbecue': 'барбекю',
    'schnitzel': 'шницель',
    'cutlet': 'котлета',
    'meatball': 'фрикаделька',
    'ground meat': 'фарш',
    
    # Общие продукты
    'bread': 'хлеб',
    'cheese': 'сыр',
    'meat': 'мясо',
    'ham': 'ветчина',
    'sausage': 'колбаса',
    'bacon': 'бекон',
    
    # Сложные и многослойные блюда
    'casserole': 'запеканка',
    'meat casserole': 'мясная запеканка',
    'baked casserole': 'запеченная запеканка',
    'layered casserole': 'слоеная запеканка',
    'ground meat casserole': 'запеканка с фаршем',
    'cheese casserole': 'сырная запеканка',
    'vegetable casserole': 'овощная запеканка',
    'layered dish': 'слоеное блюдо',
    'multi-layer dish': 'многослойное блюдо',
    'composite dish': 'составное блюдо',
    'complex dish': 'сложное блюдо',
    'quiche': 'киш',
    'pie': 'пирог',
    'meat pie': 'мясной пирог',
    'savory pie': 'несладкий пирог',
    'gratin': 'гратен',
    'potato gratin': 'картофельный гратен',
    'vegetable gratin': 'овощной гратен',
    
    # Компоненты сложных блюд
    'baked cheese topping': 'запеченный сыр сверху',
    'melted cheese topping': 'расплавленная сырная корочка',
    'cheese topping': 'сырная корочка',
    'melted cheese': 'расплавленный сыр',
    'golden cheese': 'золотистый сыр',
    'ground meat': 'фарш',
    'ground meat filling': 'мясная начинка из фарша',
    'meat filling': 'мясная начинка',
    'mixed vegetables': 'овощная смесь',
    'meat and vegetables': 'мясо с овощами',
    'vegetable filling': 'овощная начинка',
    'egg filling': 'яичная начинка',
    'cream filling': 'кремовая начинка',
    'pastry crust': 'тестовая основа',
    'pastry base': 'основа из теста',
    'dough base': 'тестовая база',
    'cream sauce': 'сливочный соус',
    'white sauce': 'белый соус',
    'bechamel sauce': 'соус бешамель',
    
    # Запеченные и фаршированные блюда
    'stuffed peppers': 'фаршированные перцы',
    'stuffed cabbage': 'голубцы',
    'stuffed tomatoes': 'фаршированные помидоры',
    'stuffed zucchini': 'фаршированные кабачки',
    'baked stuffed': 'запеченное фаршированное',
    'oven-baked': 'запеченное в духовке',
    'baked dish': 'запеченное блюдо'
}

def translate_food_name(english_name):
    """Переводим английские названия еды на русский с учетом контекста"""
    if not english_name:
        return 'Неизвестное блюдо'
    
    english_lower = english_name.lower().strip()
    
    # Точное совпадение (приоритет)
    if english_lower in FOOD_TRANSLATIONS:
        return FOOD_TRANSLATIONS[english_lower]
    
    # Частичное совпадение для сложных названий
    best_match = None
    best_match_length = 0
    
    for eng_key, rus_value in FOOD_TRANSLATIONS.items():
        # Ищем наиболее полное совпадение
        if eng_key in english_lower:
            if len(eng_key) > best_match_length:
                best_match = rus_value
                best_match_length = len(eng_key)
    
    if best_match:
        return best_match
    
    # Если точного перевода нет, возвращаем исходное название
    return english_name


class CalorieAnalyzer:
    """Класс для анализа калорий на фотографиях еды"""

    def __init__(self):
        self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)

    def encode_image(self, image_bytes):
        """Кодирование изображения в base64"""
        return base64.b64encode(image_bytes).decode('utf-8')

    def resize_image(self, image_bytes, max_size=1024):
        """Изменение размера изображения для оптимизации"""
        try:
            image = Image.open(BytesIO(image_bytes))

            # Получаем размеры
            width, height = image.size

            # Если изображение слишком большое, изменяем размер
            if max(width, height) > max_size:
                if width > height:
                    new_width = max_size
                    new_height = int((height * max_size) / width)
                else:
                    new_height = max_size
                    new_width = int((width * max_size) / height)

                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Конвертируем обратно в байты
            output = BytesIO()
            image.save(output, format='JPEG', quality=85)
            return output.getvalue()

        except Exception as e:
            logger.error(f"Ошибка при изменении размера изображения: {e}")
            return image_bytes

    async def analyze_food_image(self, image_bytes):
        """
        Анализ изображения еды и подсчет калорий
        
        Args:
            image_bytes: Байты изображения
            
        Returns:
            dict: Результат анализа с калориями и питательными веществами
        """
        try:
            logger.info("Начинаем анализ изображения")
            
            # Проверяем API ключ в самом начале
            if not config.OPENAI_API_KEY:
                logger.error("OPENAI_API_KEY не установлен")
                return self._create_fallback_result("API ключ не найден")
            
            # Проверяем размер изображения
            logger.info(f"Размер исходного изображения: {len(image_bytes)} байт")
            if len(image_bytes) == 0:
                logger.error("Пустое изображение")
                return self._create_fallback_result("Пустое изображение")
            
            # Изменяем размер изображения
            resized_image = self.resize_image(image_bytes)
            logger.info(f"Размер после изменения: {len(resized_image)} байт")
            
            # Кодируем изображение
            base64_image = self.encode_image(resized_image)
            logger.info(f"Длина base64 строки: {len(base64_image)} символов")
            
            # Отправляем запрос к OpenAI
            logger.info("Отправляем запрос к OpenAI API...")
            response = self.client.chat.completions.create(
                model=config.AI_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": config.CALORIE_PROMPT
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=config.MAX_TOKENS,
                temperature=0.1
            )
            
            logger.info("Получен ответ от OpenAI API")
            
            # Парсим ответ
            content = response.choices[0].message.content
            if not content:
                logger.error("Пустой ответ от OpenAI")
                return self._create_fallback_result("Пустой ответ от API")
                
            logger.info(f"AI ответ длиной {len(content)} символов: {content[:200]}...")
            
            # Пытаемся извлечь JSON из ответа
            ai_result = self._parse_ai_response(content)
            
            # Улучшаем анализ с помощью базы данных продуктов
            enhanced_result = self.enhance_analysis_with_database(ai_result)
            
            logger.info(f"✅ Анализ завершен. Калории: {enhanced_result.get('total_calories', 0)} "
                       f"(найдено в базе: {enhanced_result.get('database_matches', 0)}/{enhanced_result.get('total_items', 0)})")
            
            return enhanced_result
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА при анализе изображения: {e}")
            logger.error(f"Полная трассировка: {error_details}")
            
            # Возвращаем fallback результат вместо ошибки
            return self._create_fallback_result(f"Системная ошибка: {str(e)}")

    def _parse_ai_response(self, content):
        """Парсинг ответа AI с улучшенной обработкой ошибок"""
        try:
            logger.info(f"Парсим ответ AI длиной {len(content)} символов")
            
            # Ищем JSON в ответе - проверяем разные варианты
            json_patterns = [
                (content.find('{'), content.rfind('}') + 1),  # Обычный поиск
                (content.find('```json') + 7, content.find('```', content.find('```json') + 7)),  # Markdown JSON
                (content.find('```') + 3, content.rfind('```')),  # Любой code block
            ]
            
            result = None
            for start_idx, end_idx in json_patterns:
                if start_idx != -1 and end_idx > start_idx:
                    try:
                        json_str = content[start_idx:end_idx].strip()
                        logger.info(f"Пытаемся парсить JSON: {json_str[:200]}...")
                        result = json.loads(json_str)
                        logger.info("JSON успешно распарсен")
                        break
                    except json.JSONDecodeError:
                        continue
            
            if result is None:
                logger.error("Не удалось найти валидный JSON в ответе")
                raise ValueError("JSON не найден в ответе")

            # Валидация результата
            if not isinstance(result, dict):
                raise ValueError("Результат не является словарем")

            # Проверяем обязательные поля с дефолтными значениями
            result.setdefault('food_items', [])
            result.setdefault('total_calories', 0)
            result.setdefault('confidence', 50)

            # Убеждаемся, что food_items это список
            if not isinstance(result['food_items'], list):
                logger.warning("food_items не является списком, исправляем")
                result['food_items'] = []

            # Валидируем каждый food_item
            valid_items = []
            for item in result['food_items']:
                if isinstance(item, dict):
                    # Устанавливаем дефолтные значения для каждого элемента
                    item.setdefault('name', 'Неизвестный продукт')
                    item.setdefault('estimated_weight', '100г')
                    item.setdefault('calories', 100)
                    item.setdefault('proteins', 5)
                    item.setdefault('carbs', 10)
                    item.setdefault('fats', 5)
                    item.setdefault('certainty', 'medium')
                    valid_items.append(item)
            
            result['food_items'] = valid_items

            # Вычисляем общие питательные вещества
            total_proteins = sum(item.get('proteins', 0) for item in result['food_items'])
            total_carbs = sum(item.get('carbs', 0) for item in result['food_items'])
            total_fats = sum(item.get('fats', 0) for item in result['food_items'])

            result['total_proteins'] = total_proteins
            result['total_carbs'] = total_carbs
            result['total_fats'] = total_fats

            # Если total_calories не указан или равен 0, вычисляем его
            if result.get('total_calories', 0) == 0 and result['food_items']:
                result['total_calories'] = sum(item.get('calories', 0) for item in result['food_items'])

            logger.info(f"Итоговый результат: {result.get('total_calories', 0)} ккал, {len(result['food_items'])} продуктов")
            return result

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"КРИТИЧЕСКАЯ ошибка парсинга ответа AI: {e}")
            logger.error(f"Исходный ответ: {content}")

            # Создаем fallback результат на основе простого анализа
            return self._create_fallback_result(content)

    def _create_fallback_result(self, content):
        """Создает fallback результат когда не удается распарсить ответ AI"""
        logger.info("Создаем fallback результат")
        
        # Пытаемся найти упоминания еды в тексте
        food_keywords = ['steak', 'meat', 'chicken', 'fish', 'bread', 'rice', 'potato', 'salad', 'food', 'meal']
        found_foods = [word for word in food_keywords if word.lower() in content.lower()]
        
        if found_foods:
            food_name = f"Еда ({', '.join(found_foods[:2])})"
            calories_estimate = 400  # Средняя порция
        else:
            food_name = "Блюдо (не удалось распознать)"
            calories_estimate = 350
        
        return {
            "food_items": [{
                "name": food_name,
                "estimated_weight": "250г",
                "calories": calories_estimate,
                "proteins": 20,
                "carbs": 25,
                "fats": 15,
                "certainty": "low"
            }],
            "total_calories": calories_estimate,
            "total_proteins": 20,
            "total_carbs": 25,
            "total_fats": 15,
            "confidence": 30,
            "error": "Использован fallback анализ",
            "raw_response": content[:300]
        }

    def format_analysis_result(self, result):
        """Форматирование результата анализа для отображения пользователю"""
        # Показываем предупреждение только если действительно ничего не найдено
        if result.get('total_calories', 0) == 0:
            return f"{config.EMOJIS['warning']} Не удалось распознать еду на изображении.\n\nПопробуйте сделать более четкое фото блюда."
        
        # Заголовок
        message = f"{config.EMOJIS['food']} **Анализ блюда**\n\n"
        
        # Общие калории
        message += f"{config.EMOJIS['fire']} **Общие калории:** {result['total_calories']:.0f} ккал\n\n"
        
        # Питательные вещества
        if result.get('total_proteins', 0) > 0:
            message += f"{config.EMOJIS['muscle']} **Белки:** {result['total_proteins']:.1f}г\n"
        if result.get('total_carbs', 0) > 0:
            message += f"🍞 **Углеводы:** {result['total_carbs']:.1f}г\n"
        if result.get('total_fats', 0) > 0:
            message += f"🥑 **Жиры:** {result['total_fats']:.1f}г\n"
        
        # Детали блюд
        if result.get('food_items'):
            message += f"\n📝 **Состав:**\n"
            for i, item in enumerate(result['food_items'], 1):
                name = translate_food_name(item.get('name', 'Неизвестное блюдо'))
                calories = item.get('calories', 0)
                weight = item.get('estimated_weight', '')
                source = item.get('source', '🤖 AI анализ')
                
                message += f"{i}. {name}"
                if weight:
                    message += f" (~{weight})"
                message += f" - {calories:.0f} ккал"
                
                # Показываем источник данных
                if source != '🤖 AI анализ':
                    message += f" {source}"
                
                message += "\n"
        
        # Уверенность AI
        confidence = result.get('confidence', 0)
        if confidence > 80:
            confidence_emoji = config.EMOJIS['checkmark']
        elif confidence > 60:
            confidence_emoji = config.EMOJIS['warning']
        else:
            confidence_emoji = config.EMOJIS['error']
        
        message += f"\n{confidence_emoji} **Уверенность анализа:** {confidence:.0f}%"
        
        # Добавляем информацию об ошибках или fallback
        if result.get('error') and confidence < 50:
            message += f"\n\n⚠️ *Примечание: {result['error']}*"
        
        return message
    
    def enhance_analysis_with_database(self, ai_result):
        """Улучшает анализ ИИ с помощью базы данных продуктов"""
        logger.info("🔍 Улучшаем анализ с помощью базы данных продуктов...")
        
        try:
            enhanced_items = []
            total_calories_enhanced = 0
            database_matches = 0
            
            for item in ai_result.get('food_items', []):
                original_name = item.get('name', '')
                estimated_weight = self._extract_weight_from_item(item)
                
                logger.info(f"🔍 Ищем '{original_name}' в базе данных (вес: {estimated_weight}г)")
                
                # Поиск в базе данных
                nutrition_info = food_database.get_nutrition_info(original_name, estimated_weight)
                
                if nutrition_info:
                    # Найдено в базе данных - используем точные данные
                    database_matches += 1
                    enhanced_item = {
                        'name': nutrition_info['name'],
                        'estimated_weight': f"{nutrition_info['weight_g']}г",
                        'calories': nutrition_info['total_calories'],
                        'proteins': nutrition_info.get('protein', item.get('proteins', 0)),
                        'carbs': nutrition_info.get('carbs', item.get('carbs', 0)),
                        'fats': nutrition_info.get('fat', item.get('fats', 0)),
                        'source': f"📊 {nutrition_info['source']}",
                        'match_score': nutrition_info.get('match_score', 0),
                        'calories_per_100g': nutrition_info['calories_per_100g']
                    }
                    
                    logger.info(f"✅ Найдено в {nutrition_info['source']}: {nutrition_info['name']} "
                              f"= {nutrition_info['total_calories']} ккал")
                else:
                    # Не найдено в базе - используем данные ИИ
                    enhanced_item = item.copy()
                    enhanced_item['source'] = "🤖 AI анализ"
                    logger.info(f"⚠️ Не найдено в базе: '{original_name}', используем AI анализ")
                
                enhanced_items.append(enhanced_item)
                total_calories_enhanced += enhanced_item.get('calories', 0)
            
            # Создаем улучшенный результат
            enhanced_result = ai_result.copy()
            enhanced_result['food_items'] = enhanced_items
            enhanced_result['total_calories'] = round(total_calories_enhanced)
            enhanced_result['database_matches'] = database_matches
            enhanced_result['total_items'] = len(enhanced_items)
            
            # Увеличиваем confidence если найдены совпадения в базе
            original_confidence = enhanced_result.get('confidence', 70)
            if database_matches > 0:
                confidence_boost = min(20, database_matches * 10)  # До +20% за совпадения
                enhanced_result['confidence'] = min(95, original_confidence + confidence_boost)
                logger.info(f"📈 Confidence повышен с {original_confidence}% до {enhanced_result['confidence']}% "
                          f"(найдено {database_matches}/{len(enhanced_items)} в базе)")
            
            logger.info(f"✅ Анализ улучшен: {database_matches}/{len(enhanced_items)} продуктов найдено в базе")
            return enhanced_result
            
        except Exception as e:
            logger.error(f"❌ Ошибка при улучшении анализа: {e}")
            # Возвращаем оригинальный результат при ошибке
            return ai_result
    
    def _extract_weight_from_item(self, item):
        """Извлекает вес в граммах из описания продукта"""
        try:
            weight_str = item.get('estimated_weight', '0г')
            # Удаляем 'г' и пробелы, конвертируем в float
            weight = float(weight_str.replace('г', '').strip())
            return max(weight, 50)  # Минимум 50г
        except:
            # Если не удалось извлечь, используем калории для оценки
            calories = item.get('calories', 100)
            # Примерная оценка: 2.5 ккал/г для среднего продукта
            return max(50, round(calories / 2.5))

# Создаем глобальный экземпляр анализатора
analyzer = CalorieAnalyzer()