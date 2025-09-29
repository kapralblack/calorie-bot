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
        # Супы
        'борщ': {'calories_per_100g': 80, 'typical_serving': 300, 'category': 'soup'},
        'щи': {'calories_per_100g': 60, 'typical_serving': 300, 'category': 'soup'},
        'солянка': {'calories_per_100g': 90, 'typical_serving': 300, 'category': 'soup'},
        'харчо': {'calories_per_100g': 85, 'typical_serving': 300, 'category': 'soup'},
        'рассольник': {'calories_per_100g': 70, 'typical_serving': 300, 'category': 'soup'},
        
        # Пельмени и мантры
        'пельмени': {'calories_per_100g': 280, 'typical_serving': 200, 'category': 'main'},
        'вареники': {'calories_per_100g': 220, 'typical_serving': 200, 'category': 'main'},
        'мантры': {'calories_per_100g': 250, 'typical_serving': 200, 'category': 'main'},
        'хинкали': {'calories_per_100g': 240, 'typical_serving': 180, 'category': 'main'},
        
        # Блины и оладьи
        'блины': {'calories_per_100g': 230, 'typical_serving': 150, 'category': 'main'},
        'оладьи': {'calories_per_100g': 260, 'typical_serving': 120, 'category': 'main'},
        'сырники': {'calories_per_100g': 280, 'typical_serving': 120, 'category': 'main'},
        
        # Каши
        'гречка': {'calories_per_100g': 132, 'typical_serving': 200, 'category': 'side'},
        'рис': {'calories_per_100g': 116, 'typical_serving': 200, 'category': 'side'},
        'овсянка': {'calories_per_100g': 88, 'typical_serving': 200, 'category': 'side'},
        'пшенная каша': {'calories_per_100g': 90, 'typical_serving': 200, 'category': 'side'},
        
        # Напитки
        'компот': {'calories_per_100g': 60, 'typical_serving': 250, 'category': 'drink'},
        'морс': {'calories_per_100g': 50, 'typical_serving': 250, 'category': 'drink'},
        'квас': {'calories_per_100g': 30, 'typical_serving': 250, 'category': 'drink'},
        'кисель': {'calories_per_100g': 80, 'typical_serving': 200, 'category': 'drink'},
        
        # Мясные блюда
        'котлеты': {'calories_per_100g': 280, 'typical_serving': 150, 'category': 'main'},
        'тефтели': {'calories_per_100g': 250, 'typical_serving': 150, 'category': 'main'},
        'гуляш': {'calories_per_100g': 180, 'typical_serving': 200, 'category': 'main'},
        'плов': {'calories_per_100g': 190, 'typical_serving': 250, 'category': 'main'},
        
        # Рестораны
        'теремок_блин': {'calories_per_100g': 280, 'typical_serving': 220, 'category': 'restaurant'},
        'теремок_борщ': {'calories_per_100g': 85, 'typical_serving': 300, 'category': 'restaurant'},
        'теремок_морс': {'calories_per_100g': 45, 'typical_serving': 300, 'category': 'restaurant'},
    }
    
    def search_food(self, query: str, max_results: int = 5) -> List[Dict]:
        """Поиск в российской базе данных"""
        query = query.lower().strip()
        
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
            if score >= 60:  # Минимальный порог совпадения
                food_data = self.RUSSIAN_FOODS[match]
                results.append({
                    'id': f'ru_{match}',
                    'name': match.title(),
                    'source': 'russian_database',
                    'calories_per_100g': food_data['calories_per_100g'],
                    'typical_serving_g': food_data['typical_serving'],
                    'category': food_data['category'],
                    'match_score': score
                })
        
        return results

class FoodDatabaseManager:
    """Менеджер для работы с несколькими базами данных продуктов"""
    
    def __init__(self):
        self.fatsecret = FatSecretAPI()
        self.russian_db = RussianFoodDatabase()
        logger.info("FoodDatabaseManager инициализирован")
    
    def search_food(self, query: str, prefer_russian: bool = True) -> List[Dict]:
        """Поиск продукта во всех доступных базах"""
        all_results = []
        
        # Сначала ищем в российской базе
        if prefer_russian:
            russian_results = self.russian_db.search_food(query)
            all_results.extend(russian_results)
        
        # Затем в FatSecret (если есть API ключи)
        if self.fatsecret.enabled:
            fatsecret_results = self.fatsecret.search_food(query)
            for result in fatsecret_results:
                result['source'] = 'fatsecret'
            all_results.extend(fatsecret_results)
        
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
        """Получает точную информацию о калориях и БЖУ для продукта"""
        search_results = self.search_food(food_name)
        
        if not search_results:
            return None
        
        # Берем лучший результат
        best_match = search_results[0]
        
        if best_match.get('source') == 'russian_database':
            # Используем данные из российской базы
            calories_per_100g = best_match['calories_per_100g']
            total_calories = (calories_per_100g * estimated_weight_g) / 100
            
            return {
                'name': best_match['name'],
                'source': 'russian_database',
                'weight_g': estimated_weight_g,
                'calories_per_100g': calories_per_100g,
                'total_calories': round(total_calories),
                'match_score': best_match.get('match_score', 0),
                'typical_serving_g': best_match.get('typical_serving_g')
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
                    'fat': round((nutrition['fat'] * estimated_weight_g) / 100, 1)
                }
        
        return None

# Создаем глобальный экземпляр
food_database = FoodDatabaseManager()
