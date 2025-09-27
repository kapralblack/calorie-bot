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

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка OpenAI
openai.api_key = config.OPENAI_API_KEY

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
            # Изменяем размер изображения
            resized_image = self.resize_image(image_bytes)
            
            # Кодируем изображение
            base64_image = self.encode_image(resized_image)
            
            # Отправляем запрос к OpenAI
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
            
            # Парсим ответ
            content = response.choices[0].message.content
            logger.info(f"AI ответ: {content}")
            
            # Пытаемся извлечь JSON из ответа
            result = self._parse_ai_response(content)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при анализе изображения: {e}")
            return {
                "food_items": [],
                "total_calories": 0,
                "confidence": 0,
                "error": str(e)
            }
    
    def _parse_ai_response(self, content):
        """Парсинг ответа AI"""
        try:
            # Ищем JSON в ответе
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = content[start_idx:end_idx]
                result = json.loads(json_str)
                
                # Валидация результата
                if not isinstance(result, dict):
                    raise ValueError("Результат не является словарем")
                
                # Проверяем обязательные поля
                required_fields = ['food_items', 'total_calories', 'confidence']
                for field in required_fields:
                    if field not in result:
                        result[field] = 0 if field != 'food_items' else []
                
                # Убеждаемся, что food_items это список
                if not isinstance(result['food_items'], list):
                    result['food_items'] = []
                
                # Вычисляем общие питательные вещества
                total_proteins = sum(item.get('proteins', 0) for item in result['food_items'])
                total_carbs = sum(item.get('carbs', 0) for item in result['food_items'])
                total_fats = sum(item.get('fats', 0) for item in result['food_items'])
                
                result['total_proteins'] = total_proteins
                result['total_carbs'] = total_carbs
                result['total_fats'] = total_fats
                
                return result
            else:
                raise ValueError("JSON не найден в ответе")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Ошибка парсинга ответа AI: {e}")
            
            # Пытаемся извлечь хотя бы базовую информацию
            return {
                "food_items": [],
                "total_calories": 0,
                "total_proteins": 0,
                "total_carbs": 0,
                "total_fats": 0,
                "confidence": 0,
                "error": "Не удалось распознать еду на изображении",
                "raw_response": content
            }
    
    def format_analysis_result(self, result):
        """Форматирование результата анализа для отображения пользователю"""
        if result.get('confidence', 0) == 0 or result.get('total_calories', 0) == 0:
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
                name = item.get('name', 'Неизвестное блюдо')
                calories = item.get('calories', 0)
                portion = item.get('portion_size', '')
                
                message += f"{i}. {name}"
                if portion:
                    message += f" ({portion})"
                message += f" - {calories:.0f} ккал\n"
        
        # Уверенность AI
        confidence = result.get('confidence', 0)
        if confidence > 80:
            confidence_emoji = config.EMOJIS['checkmark']
        elif confidence > 60:
            confidence_emoji = config.EMOJIS['warning']
        else:
            confidence_emoji = config.EMOJIS['error']
        
        message += f"\n{confidence_emoji} **Уверенность анализа:** {confidence:.0f}%"
        
        return message

# Создаем глобальный экземпляр анализатора
analyzer = CalorieAnalyzer()
