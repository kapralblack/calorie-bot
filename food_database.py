"""
Модуль для работы с базами данных продуктов питания
Поддерживает FatSecret API и Open Food Facts
"""

import requests
import hmac
import hashlib
import base64
import urllib.parse
import time
from typing import Dict, List, Optional, Tuple
import logging
from fuzzywuzzy import fuzz, process
import config

logger = logging.getLogger(__name__)

class FatSecretAPI:
    """Класс для работы с FatSecret Platform API"""
    
    def __init__(self):
        self.consumer_key = config.FATSECRET_CONSUMER_KEY
        self.consumer_secret = config.FATSECRET_CONSUMER_SECRET
        self.base_url = "https://platform.fatsecret.com/rest/server.api"
        
        if not self.consumer_key or not self.consumer_secret:
            logger.warning("FatSecret API ключи не настроены. Функция поиска продуктов недоступна.")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("FatSecret API инициализирован")
    
    def _generate_oauth_signature(self, method: str, url: str, params: Dict) -> str:
        """Генерирует OAuth 1.0 подпись для FatSecret API"""
        if not self.enabled:
            return ""
            
        # OAuth параметры
        oauth_params = {
            'oauth_consumer_key': self.consumer_key,
            'oauth_nonce': str(int(time.time() * 1000000)),
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': str(int(time.time())),
            'oauth_version': '1.0'
        }
        
        # Объединяем все параметры
        all_params = {**params, **oauth_params}
        
        # Создаем строку параметров
        param_string = '&'.join([f'{k}={urllib.parse.quote(str(v), safe="")}' 
                                for k, v in sorted(all_params.items())])
        
        # Создаем базовую строку для подписи
        base_string = f'{method}&{urllib.parse.quote(url, safe="")}&{urllib.parse.quote(param_string, safe="")}'
        
        # Создаем ключ для подписи
        signing_key = f'{urllib.parse.quote(self.consumer_secret, safe="")}&'
        
        # Генерируем подпись
        signature = base64.b64encode(
            hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
        ).decode()
        
        return signature
    
    def search_food(self, query: str, max_results: int = 5) -> List[Dict]:
        """Поиск продуктов в FatSecret базе данных"""
        if not self.enabled:
            return []
            
        try:
            params = {
                'method': 'foods.search',
                'search_expression': query,
                'format': 'json'
            }
            
            # Генерируем OAuth подпись
            signature = self._generate_oauth_signature('GET', self.base_url, params)
            
            # Добавляем OAuth параметры для запроса
            oauth_params = {
                'oauth_consumer_key': self.consumer_key,
                'oauth_nonce': str(int(time.time() * 1000000)),
                'oauth_signature': signature,
                'oauth_signature_method': 'HMAC-SHA1',
                'oauth_timestamp': str(int(time.time())),
                'oauth_version': '1.0'
            }
            
            all_params = {**params, **oauth_params}
            
            # Выполняем запрос
            response = requests.get(self.base_url, params=all_params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'foods' in data and 'food' in data['foods']:
                foods = data['foods']['food']
                if isinstance(foods, dict):
                    foods = [foods]  # Если один результат
                
                results = []
                for food in foods[:max_results]:
                    results.append({
                        'id': food.get('food_id'),
                        'name': food.get('food_name'),
                        'type': food.get('food_type'),
                        'url': food.get('food_url')
                    })
                
                logger.info(f"FatSecret: найдено {len(results)} продуктов для '{query}'")
                return results
            else:
                logger.info(f"FatSecret: продукты не найдены для '{query}'")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка поиска в FatSecret API: {e}")
            return []
    
    def get_food_details(self, food_id: str) -> Optional[Dict]:
        """Получает детальную информацию о продукте по ID"""
        if not self.enabled:
            return None
            
        try:
            params = {
                'method': 'food.get',
                'food_id': food_id,
                'format': 'json'
            }
            
            signature = self._generate_oauth_signature('GET', self.base_url, params)
            
            oauth_params = {
                'oauth_consumer_key': self.consumer_key,
                'oauth_nonce': str(int(time.time() * 1000000)),
                'oauth_signature': signature,
                'oauth_signature_method': 'HMAC-SHA1',
                'oauth_timestamp': str(int(time.time())),
                'oauth_version': '1.0'
            }
            
            all_params = {**params, **oauth_params}
            
            response = requests.get(self.base_url, params=all_params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'food' in data:
                food = data['food']
                servings = food.get('servings', {}).get('serving', [])
                
                # Ищем информацию на 100г
                nutrition_per_100g = None
                for serving in servings if isinstance(servings, list) else [servings]:
                    if serving.get('metric_serving_unit') == 'g' and serving.get('metric_serving_amount') == '100.000':
                        nutrition_per_100g = {
                            'calories': float(serving.get('calories', 0)),
                            'protein': float(serving.get('protein', 0)),
                            'carbs': float(serving.get('carbohydrate', 0)),
                            'fat': float(serving.get('fat', 0)),
                            'fiber': float(serving.get('fiber', 0)),
                            'sugar': float(serving.get('sugar', 0))
                        }
                        break
                
                return {
                    'id': food.get('food_id'),
                    'name': food.get('food_name'),
                    'type': food.get('food_type'),
                    'nutrition_per_100g': nutrition_per_100g,
                    'servings': servings
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения деталей продукта {food_id}: {e}")
            return None
        
        return None

class RussianFoodDatabase:
    """Статическая база российских продуктов и блюд"""
    
    RUSSIAN_FOODS = {
        # Супы (калории на основе FatSecret)
        'борщ': {'calories_per_100g': 93, 'typical_serving': 300, 'category': 'soup'},  # 252 ккал / 271г = 93 ккал/100г
        'щи': {'calories_per_100g': 60, 'typical_serving': 300, 'category': 'soup'},
        'солянка': {'calories_per_100g': 90, 'typical_serving': 300, 'category': 'soup'},
        'харчо': {'calories_per_100g': 85, 'typical_serving': 300, 'category': 'soup'},
        'рассольник': {'calories_per_100g': 70, 'typical_serving': 300, 'category': 'soup'},
        
        # Пельмени и мантры (калории на основе FatSecret)
        'пельмени': {'calories_per_100g': 197, 'typical_serving': 200, 'category': 'main'},  # 296 ккал / 150г = 197 ккал/100г
        'вареники': {'calories_per_100g': 220, 'typical_serving': 200, 'category': 'main'},
        'мантры': {'calories_per_100g': 250, 'typical_serving': 200, 'category': 'main'},
        'хинкали': {'calories_per_100g': 240, 'typical_serving': 180, 'category': 'main'},
        
        # Блины и оладьи (калории на основе FatSecret)
        'блины': {'calories_per_100g': 267, 'typical_serving': 250, 'category': 'main'},  # 590 ккал / 221г = 267 ккал/100г
        'оладьи': {'calories_per_100g': 260, 'typical_serving': 120, 'category': 'main'},
        'сырники': {'calories_per_100g': 280, 'typical_serving': 300, 'category': 'main'},  # Сырники калорийнее блинов
        
        # Каши
        'гречка': {'calories_per_100g': 132, 'typical_serving': 200, 'category': 'side'},
        'рис': {'calories_per_100g': 116, 'typical_serving': 200, 'category': 'side'},
        'овсянка': {'calories_per_100g': 88, 'typical_serving': 200, 'category': 'side'},
        'пшенная каша': {'calories_per_100g': 90, 'typical_serving': 200, 'category': 'side'},
        
        # Напитки (калории на основе FatSecret)
        'компот': {'calories_per_100g': 60, 'typical_serving': 250, 'category': 'drink'},
        'морс': {'calories_per_100g': 40, 'typical_serving': 300, 'category': 'drink'},  # 120 ккал / 300мл = 40 ккал/100мл
        'квас': {'calories_per_100g': 30, 'typical_serving': 250, 'category': 'drink'},
        'кисель': {'calories_per_100g': 80, 'typical_serving': 200, 'category': 'drink'},
        
        # Мясные блюда
        'котлеты': {'calories_per_100g': 280, 'typical_serving': 150, 'category': 'main'},
        'тефтели': {'calories_per_100g': 250, 'typical_serving': 150, 'category': 'main'},
        'гуляш': {'calories_per_100g': 180, 'typical_serving': 200, 'category': 'main'},
        'плов': {'calories_per_100g': 190, 'typical_serving': 250, 'category': 'main'},
        
        # Стейки и говядина (усредненные значения)
        'стейк говяжий': {'calories_per_100g': 220, 'typical_serving': 250, 'category': 'main'},
        'стейк': {'calories_per_100g': 220, 'typical_serving': 250, 'category': 'main'},
        'стейк рибай': {'calories_per_100g': 250, 'typical_serving': 250, 'category': 'main'},
        'говядина': {'calories_per_100g': 187, 'typical_serving': 200, 'category': 'main'},
        'говядина гриль': {'calories_per_100g': 195, 'typical_serving': 200, 'category': 'main'},
        
        # Курица
        'курица': {'calories_per_100g': 165, 'typical_serving': 200, 'category': 'main'},
        'курица гриль': {'calories_per_100g': 142, 'typical_serving': 200, 'category': 'main'},
        'куриная грудка': {'calories_per_100g': 113, 'typical_serving': 150, 'category': 'main'},
        'куриное филе': {'calories_per_100g': 113, 'typical_serving': 150, 'category': 'main'},
        
        # Свинина
        'свинина': {'calories_per_100g': 242, 'typical_serving': 200, 'category': 'main'},
        'свинина гриль': {'calories_per_100g': 250, 'typical_serving': 200, 'category': 'main'},
        'свиная отбивная': {'calories_per_100g': 260, 'typical_serving': 150, 'category': 'main'},
        
        # Дополнительные продукты
        'сок': {'calories_per_100g': 45, 'typical_serving': 250, 'category': 'drink'},
        'банановые чипсы': {'calories_per_100g': 519, 'typical_serving': 30, 'category': 'snack'},
        'миндаль': {'calories_per_100g': 579, 'typical_serving': 30, 'category': 'nuts'},
        'изюм': {'calories_per_100g': 299, 'typical_serving': 50, 'category': 'snack'},
        'помидор': {'calories_per_100g': 18, 'typical_serving': 100, 'category': 'vegetable'},
        'томат': {'calories_per_100g': 18, 'typical_serving': 100, 'category': 'vegetable'},
        
        # Сметана (калории на основе FatSecret)
        'сметана': {'calories_per_100g': 202, 'typical_serving': 50, 'category': 'dairy'},  # 101 ккал / 50г = 202 ккал/100г
        
        # Рестораны (обновленные калории)
        'теремок_блин': {'calories_per_100g': 267, 'typical_serving': 250, 'category': 'restaurant'},
        'теремок_борщ': {'calories_per_100g': 93, 'typical_serving': 300, 'category': 'restaurant'},
        'теремок_морс': {'calories_per_100g': 40, 'typical_serving': 300, 'category': 'restaurant'},
        'теремок_пельмени': {'calories_per_100g': 197, 'typical_serving': 200, 'category': 'restaurant'},
        'теремок_сметана': {'calories_per_100g': 202, 'typical_serving': 50, 'category': 'restaurant'},
    }
    
    def search_food(self, query: str, max_results: int = 5) -> List[Dict]:
        """Поиск в российской базе данных"""
        query = query.lower().strip()
        
        # Словарь переводов английских названий на русские
        english_to_russian = {
            # Основные блюда
            'borscht': 'борщ',
            'borscht with sour cream': 'борщ',
            'dumplings': 'пельмени', 
            'dumplings with sour cream': 'пельмени',
            'stuffed crepe': 'блины',
            'crepe': 'блины',
            'blini': 'блины',
            'pancake': 'блины',
            
            # Сырники
            'cottage cheese pancakes': 'сырники',
            'syrniki': 'сырники',
            'cheese pancakes': 'сырники',
            'thick pancakes': 'сырники',
            'golden pancakes': 'сырники',
            'fried cottage cheese': 'сырники',
            'cottage cheese fritters': 'сырники',
            
            'buckwheat': 'гречка',
            'rice': 'рис',
            'oatmeal': 'овсянка',
            
            # Напитки
            'juice': 'сок',
            'glass of juice': 'сок',
            'compote': 'компот',
            'morse': 'морс',
            'kvass': 'квас',
            'kissel': 'кисель',
            
            # Мясные блюда
            'cutlets': 'котлеты',
            'meatballs': 'тефтели',
            'goulash': 'гуляш',
            'pilaf': 'плов',
            
            # Стейки и говядина
            'steak': 'стейк говяжий',
            'beef steak': 'стейк говяжий',
            'grilled beef steak': 'стейк говяжий',
            'grilled steak': 'стейк говяжий',
            'ribeye steak': 'стейк рибай',
            'ribeye': 'стейк рибай',
            'sirloin steak': 'стейк',
            'beef': 'говядина',
            'grilled beef': 'говядина',
            
            # Курица
            'chicken': 'курица',
            'grilled chicken': 'курица гриль',
            'chicken breast': 'куриная грудка',
            'chicken fillet': 'куриное филе',
            
            # Свинина
            'pork': 'свинина',
            'pork chop': 'свиная отбивная',
            'grilled pork': 'свинина гриль',
            
            # Супы
            'shchi': 'щи',
            'solyanka': 'солянка',
            'kharcho': 'харчо',
            'rassolnik': 'рассольник',
            
            # Другие блюда
            'vareniki': 'вареники',
            'mantry': 'мантры',
            'khinkali': 'хинкали',
            'syrniki': 'сырники',
            'oladyi': 'оладьи',
            
            # Орехи и снеки  
            'dried banana chips': 'банановые чипсы',
            'banana chips': 'банановые чипсы',
            'almonds': 'миндаль',
            'raisins': 'изюм',
            
            # Овощи
            'sliced tomato': 'помидор',
            'tomato': 'помидор',
            'tomatoes': 'помидор',
            
            # Молочные продукты
            'sour cream': 'сметана',
            'smetana': 'сметана'
        }
        
        # Переводим на русский если нужно
        original_query = query
        if query in english_to_russian:
            translated_query = english_to_russian[query]
            logger.info(f"🔄 Переведено '{original_query}' → '{translated_query}'")
            query = translated_query
        
        # Точное совпадение
        if query in self.RUSSIAN_FOODS:
            food_data = self.RUSSIAN_FOODS[query]
            return [{
                'id': f'ru_{query}',
                'name': query.title(),
                'source': 'russian_database',
                'calories_per_100g': food_data['calories_per_100g'],
                'typical_serving_g': food_data['typical_serving'],
                'category': food_data['category'],
                'match_score': 100
            }]
        
        # Нечеткий поиск
        matches = process.extract(query, self.RUSSIAN_FOODS.keys(), limit=max_results, scorer=fuzz.partial_ratio)
        
        results = []
        for match, score in matches:
            if score >= 70:  # Повышен порог для лучшей точности
                food_data = self.RUSSIAN_FOODS[match]
                results.append({
                    'id': f'ru_{match}',
                    'name': match.title(),
                    'source': 'russian',
                    'calories_per_100g': food_data['calories_per_100g'],
                    'typical_serving_g': food_data['typical_serving'],
                    'category': food_data['category'],
                    'match_score': score
                })
        
        # Если ничего не нашли в русской базе, пробуем FatSecret
        if not results:
            logger.info(f"🔍 Не нашли '{query}' в русской базе, ищем в FatSecret...")
            fatsecret = FatSecretAPI()
            fatsecret_results = fatsecret.search_food(original_query)
            if fatsecret_results:
                return fatsecret_results
        
        return results

class FoodDatabaseManager:
    """Менеджер для работы с несколькими базами данных продуктов"""
    
    def __init__(self):
        self.fatsecret = FatSecretAPI()
        self.russian_db = RussianFoodDatabase()
        
        # Умная математическая модель для коррекции
        self.CORRECTION_FACTORS = {
            # Типичные веса для российских блюд (на основе FatSecret)
            'typical_weights': {
                'борщ': 300,  # 271г в FatSecret, но обычно 300г порция
                'пельмени': 200,  # 150г в FatSecret, но обычно 200г порция  
                'блины': 250,  # 221г в FatSecret, но обычно 250г порция
                'сырники': 300,  # Сырники обычно порция 300г (7 штук по ~43г)
                'морс': 300,  # 300мл в FatSecret
                'сметана': 50,  # 50г в FatSecret
                'сок': 250,  # 250мл типичная порция
            },
            # Коэффициенты коррекции калорий для российских блюд
            'calorie_corrections': {
                'борщ': 1.0,  # Борщ: 85 ккал/100г * 3 = 255 ккал (близко к FatSecret 252)
                'пельмени': 1.0,  # Пельмени: 280 ккал/100г * 2 = 560 ккал (FatSecret 296 для 150г)
                'блины': 1.0,  # Блины: 200 ккал/100г * 2.5 = 500 ккал (FatSecret 590 для 221г)
                'сырники': 1.0,  # Сырники: 280 ккал/100г * 3 = 840 ккал (калорийнее блинов)
                'морс': 1.0,  # Морс: 45 ккал/100г * 3 = 135 ккал (FatSecret 120 для 300мл)
                'сметана': 1.0,  # Сметана: 200 ккал/100г * 0.5 = 100 ккал (FatSecret 101 для 50г)
            }
        }
        
        logger.info("FoodDatabaseManager инициализирован с умной коррекцией")
    
    def search_food(self, query: str, prefer_russian: bool = True) -> List[Dict]:
        """Поиск продукта во всех доступных базах"""
        logger.info(f"🔍 FoodDatabaseManager: ищем '{query}' во всех базах")
        all_results = []
        
        # Сначала ищем в российской базе
        if prefer_russian:
            logger.info(f"🇷🇺 Поиск в российской базе данных...")
            russian_results = self.russian_db.search_food(query)
            if russian_results:
                logger.info(f"✅ Российская база: найдено {len(russian_results)} результатов")
                all_results.extend(russian_results)
            else:
                logger.info(f"❌ Российская база: ничего не найдено")
        
        # Затем в FatSecret (если есть API ключи)
        if self.fatsecret.enabled:
            logger.info(f"🌍 Поиск в FatSecret API...")
            fatsecret_results = self.fatsecret.search_food(query)
            for result in fatsecret_results:
                result['source'] = 'fatsecret'
            if fatsecret_results:
                logger.info(f"✅ FatSecret: найдено {len(fatsecret_results)} результатов")
                all_results.extend(fatsecret_results)
            else:
                logger.info(f"❌ FatSecret: ничего не найдено")
        else:
            logger.info(f"⚠️ FatSecret API отключен (нет ключей)")
        
        # Сортируем по релевантности (российские продукты приоритетнее)
        def sort_key(item):
            priority = 0
            if item.get('source') == 'russian_database':
                priority += 1000
            if item.get('match_score'):
                priority += item['match_score']
            return priority
        
        all_results.sort(key=sort_key, reverse=True)
        
        return all_results[:10]  # Возвращаем топ 10
    
    def get_nutrition_info(self, food_name: str, estimated_weight_g: float) -> Dict:
        """Получает точную информацию о калориях и БЖУ для продукта с умной коррекцией"""
        logger.info(f"📊 Получаем питательную информацию для '{food_name}' ({estimated_weight_g}г)")
        search_results = self.search_food(food_name)
        
        if not search_results:
            logger.info(f"❌ Питательная информация не найдена для '{food_name}'")
            return None
        
        # Берем лучший результат
        best_match = search_results[0]
        logger.info(f"🎯 Лучший результат: {best_match.get('name')} из {best_match.get('source')}")
        
        if best_match.get('source') == 'russian_database':
            # Применяем умную коррекцию для российских блюд
            food_key = best_match['name'].lower()
            corrected_weight = self._apply_weight_correction(food_key, estimated_weight_g)
            corrected_calories = self._apply_calorie_correction(food_key, best_match, corrected_weight)
            
            logger.info(f"🧮 Коррекция: {estimated_weight_g}г → {corrected_weight}г, "
                       f"калории: {best_match['calories_per_100g'] * corrected_weight / 100:.0f} → {corrected_calories}")
            
            return {
                'name': best_match['name'],
                'source': 'russian_database_corrected',
                'weight_g': corrected_weight,
                'calories_per_100g': best_match['calories_per_100g'],
                'total_calories': corrected_calories,
                'match_score': best_match.get('match_score', 0),
                'typical_serving_g': best_match.get('typical_serving_g'),
                'correction_applied': True
            }
            
        elif best_match.get('source') == 'fatsecret' and self.fatsecret.enabled:
            # Получаем детальную информацию из FatSecret
            details = self.fatsecret.get_food_details(best_match['id'])
            if details and details.get('nutrition_per_100g'):
                nutrition = details['nutrition_per_100g']
                total_calories = (nutrition['calories'] * estimated_weight_g) / 100
                
                return {
                    'name': details['name'],
                    'source': 'fatsecret',
                    'weight_g': estimated_weight_g,
                    'calories_per_100g': nutrition['calories'],
                    'total_calories': round(total_calories),
                    'protein': round((nutrition['protein'] * estimated_weight_g) / 100, 1),
                    'carbs': round((nutrition['carbs'] * estimated_weight_g) / 100, 1),
                    'fat': round((nutrition['fat'] * estimated_weight_g) / 100, 1),
                    'correction_applied': False
                }
        
        return None
    
    def _apply_weight_correction(self, food_key: str, estimated_weight: float) -> int:
        """Применяет коррекцию веса на основе типичных порций"""
        typical_weight = self.CORRECTION_FACTORS['typical_weights'].get(food_key)
        
        if typical_weight:
            # Если оцененный вес сильно отличается от типичного, используем типичный
            if abs(estimated_weight - typical_weight) > typical_weight * 0.5:
                logger.info(f"🔧 Коррекция веса: {estimated_weight}г → {typical_weight}г (типичная порция)")
                return typical_weight
        
        return int(estimated_weight)
    
    def _apply_calorie_correction(self, food_key: str, food_data: Dict, corrected_weight: int) -> int:
        """Применяет коррекцию калорий на основе данных FatSecret"""
        base_calories = food_data['calories_per_100g'] * corrected_weight / 100
        correction_factor = self.CORRECTION_FACTORS['calorie_corrections'].get(food_key, 1.0)
        
        corrected_calories = int(base_calories * correction_factor)
        
        if correction_factor != 1.0:
            logger.info(f"🔧 Коррекция калорий: {base_calories:.0f} → {corrected_calories} "
                       f"(коэффициент: {correction_factor})")
        
        return corrected_calories

# Создаем глобальный экземпляр
food_database = FoodDatabaseManager()
