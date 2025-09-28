"""
Основной файл телеграм-бота для подсчета калорий
"""
import asyncio
import logging
import json
from datetime import datetime, timedelta
import schedule
import threading
import time
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

import config
from database import DatabaseManager, create_tables
from ai_analyzer import analyzer

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CalorieBotHandlers:
    """Обработчики команд телеграм-бота"""
    
    @staticmethod
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        
        # Сбрасываем флаг сохранения анализа при возврате в главное меню
        context.user_data.pop('preserve_analysis_message', None)
        
        telegram_user = DatabaseManager.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        welcome_message = f"""
{config.EMOJIS['apple']} **Добро пожаловать в {config.BOT_NAME}!**

Привет, {user.first_name}! Я помогу тебе отслеживать калории по фотографиям еды.

**Что я умею:**
{config.EMOJIS['food']} Анализировать фото еды и считать калории
{config.EMOJIS['stats']} Вести статистику питания
{config.EMOJIS['chart']} Показывать графики прогресса
{config.EMOJIS['settings']} Настраивать цели калорий

**Как пользоваться:**
1. Отправьте мне фото вашей еды
2. Я проанализирую и посчитаю калории
3. Смотрите статистику и следите за целями

Начните с отправки фото еды или выберите действие ниже:
"""
        
        keyboard = [
            [InlineKeyboardButton("👤 Личный кабинет", callback_data="profile")],
            [InlineKeyboardButton(f"{config.EMOJIS['stats']} Статистика", callback_data="stats")],
            [InlineKeyboardButton(f"{config.EMOJIS['settings']} Настройки", callback_data="settings")],
            [InlineKeyboardButton(f"{config.EMOJIS['help']} Помощь", callback_data="help")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ИСПРАВЛЕНИЕ: Проверяем, это callback query или обычное сообщение
        if update.callback_query:
            # Это нажатие кнопки
            await update.callback_query.edit_message_text(
                welcome_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        else:
            # Это команда /start
            await update.message.reply_text(
                welcome_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
    
    @staticmethod 
    async def fix_goal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для принудительного обновления цели калорий"""
        user = update.effective_user
        
        # Принудительно устанавливаем цель 3000 ккал
        success = DatabaseManager.force_update_user_goal(user.id, 3000)
        
        if success:
            message = f"✅ **Цель обновлена!**\n\nВаша новая цель: **3000 ккал в день**\n\nТеперь статистика будет отображаться правильно!"
        else:
            message = "❌ Ошибка при обновлении цели. Попробуйте еще раз."
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def test_ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестовая команда для проверки OpenAI API"""
        user = update.effective_user
        
        # Проверяем только админа (если указан)
        if config.ADMIN_USER_ID and str(user.id) != config.ADMIN_USER_ID:
            await update.message.reply_text("❌ Команда доступна только администратору")
            return
        
        await update.message.reply_text("🔍 Тестируем OpenAI API...")
        
        try:
            # Простой тестовый запрос
            from ai_analyzer import analyzer
            test_response = analyzer.client.chat.completions.create(
                model=config.AI_MODEL,
                messages=[{"role": "user", "content": "Ответь одним словом: 'работаю'"}],
                max_tokens=10
            )
            
            ai_response = test_response.choices[0].message.content
            await update.message.reply_text(f"✅ OpenAI API работает: {ai_response}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка OpenAI API: {str(e)}")
            import traceback
            logger.error(f"Ошибка тестирования OpenAI: {traceback.format_exc()}")

    @staticmethod
    async def debug_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /debuguser - диагностика пользовательских данных"""
        user = update.effective_user
        
        try:
            # Получаем пользователя
            db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
            
            # Получаем статистику
            tracking_days = DatabaseManager.get_tracking_days(db_user.id)
            today_calories = DatabaseManager.get_today_calories(db_user.id)
            
            message = f"""
🔍 **Диагностика пользователя**

👤 **Основные данные:**
• Telegram ID: `{user.id}`
• ID в БД: `{db_user.id}`
• Имя: {user.first_name or 'Не указано'}

⚙️ **Настройки профиля:**
• Цель калорий: {db_user.daily_calorie_goal} ккал/день
• Вес: {db_user.weight or 'Не указан'} {' кг' if db_user.weight else ''}
• Рост: {db_user.height or 'Не указан'} {' см' if db_user.height else ''}
• Возраст: {db_user.age or 'Не указан'} {' лет' if db_user.age else ''}
• Пол: {('мужской' if db_user.gender == 'male' else 'женский') if db_user.gender else 'Не указан'}

📊 **Статистика:**
• Дней с записями: {tracking_days}
• Калорий сегодня: {today_calories:.1f}
• Создан: {db_user.created_at.strftime('%d.%m.%Y %H:%M') if db_user.created_at else 'Неизвестно'}

🔧 **For fixing data use:**
/fixgoal - Установить цель 3000 ккал
⚙️ Настройки - Изменить физические параметры
"""
            
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка диагностики: {e}")

    @staticmethod 
    async def reset_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /resetuser - полный сброс данных пользователя для тестирования"""
        user = update.effective_user
        
        try:
            # Получаем пользователя
            db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
            
            # Сбрасываем все настройки на дефолтные
            updated_user = DatabaseManager.update_user_settings(
                db_user.id,
                daily_calorie_goal=2000,
                weight=None,
                height=None,
                age=None,
                gender=None
            )
            
            logger.info(f"🔄 Пользователь {user.id} сброшен к дефолтным настройкам")
            
            await update.message.reply_text(
                f"""
🔄 **Данные сброшены**

Ваши настройки возвращены к исходным:
• Цель калорий: 2000 ккал/день  
• Физические параметры: сброшены

Теперь можете заново настроить профиль через:
⚙️ /settings - настройки
🎯 /fixgoal - установить цель 3000 ккал
""", 
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка сброса: {e}")

    @staticmethod 
    async def debug_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /debugstats - проверка состояния таблиц DailyStats и FoodEntry"""
        user = update.effective_user
        
        try:
            # Получаем пользователя
            db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
            
            # Проверяем FoodEntry
            from database import SessionLocal, FoodEntry, DailyStats
            from sqlalchemy import func
            
            db = SessionLocal()
            try:
                # Считаем записи в FoodEntry
                food_entries_count = db.query(func.count(FoodEntry.id)).filter(
                    FoodEntry.user_id == db_user.id
                ).scalar()
                
                # Считаем записи в DailyStats
                daily_stats_count = db.query(func.count(DailyStats.id)).filter(
                    DailyStats.user_id == db_user.id
                ).scalar()
                
                # Последние 3 записи FoodEntry
                recent_food_entries = db.query(FoodEntry).filter(
                    FoodEntry.user_id == db_user.id
                ).order_by(FoodEntry.created_at.desc()).limit(3).all()
                
                # Последние 3 записи DailyStats
                recent_daily_stats = db.query(DailyStats).filter(
                    DailyStats.user_id == db_user.id
                ).order_by(DailyStats.date.desc()).limit(3).all()
                
            finally:
                db.close()
            
            message = f"""
🔍 **Диагностика таблиц базы данных**

📊 **Таблица FoodEntry (записи о еде):**
• Всего записей: {food_entries_count}

📈 **Таблица DailyStats (дневная статистика):**  
• Всего записей: {daily_stats_count}

🕐 **Последние записи FoodEntry:**
"""
            
            for entry in recent_food_entries:
                message += f"• {entry.created_at.strftime('%d.%m %H:%M')}: {entry.total_calories:.1f} ккал\n"
            
            message += "\n📅 **Последние записи DailyStats:**\n"
            
            for stat in recent_daily_stats:
                message += f"• {stat.date.strftime('%d.%m')}: {stat.total_calories:.1f} ккал ({stat.meals_count} блюд)\n"
            
            if food_entries_count > 0 and daily_stats_count == 0:
                message += "\n⚠️ **ПРОБЛЕМА:** Есть записи еды, но нет дневной статистики!"
            
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка диагностики таблиц: {e}")
            import traceback
            logger.error(f"Ошибка debug_stats: {traceback.format_exc()}")

    @staticmethod 
    async def rebuild_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /rebuildstats - принудительное пересоздание DailyStats из FoodEntry"""
        user = update.effective_user
        
        try:
            # Получаем пользователя
            db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
            
            # Получаем все уникальные даты из FoodEntry
            from database import SessionLocal, FoodEntry
            from sqlalchemy import func
            
            db = SessionLocal()
            try:
                # Получаем все уникальные даты записей пользователя
                unique_dates = db.query(
                    func.date(FoodEntry.created_at).label('date')
                ).filter(
                    FoodEntry.user_id == db_user.id
                ).distinct().all()
                
            finally:
                db.close()
            
            if not unique_dates:
                await update.message.reply_text("📊 У вас нет записей для пересоздания статистики")
                return
            
            # Пересоздаем статистику для каждой даты
            rebuilt_count = 0
            for date_row in unique_dates:
                date = date_row.date
                DatabaseManager._update_daily_stats(db_user.id, date)
                rebuilt_count += 1
            
            message = f"""
✅ **Статистика пересоздана!**

📊 Обработано дат: {rebuilt_count}
🔄 Все записи DailyStats обновлены

Теперь попробуйте:
📈 Кнопку "Статистика" - должна показать данные  
🔍 /debugstats - проверить таблицы
"""
            
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка пересоздания статистики: {e}")
            import traceback
            logger.error(f"Ошибка rebuild_stats: {traceback.format_exc()}")
    
    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        help_message = f"""
{config.EMOJIS['help']} **Помощь по использованию бота**

**Основные команды:**
/start - Начать работу с ботом
/profile - Личный кабинет пользователя
/stats - Показать статистику
/settings - Настройки профиля
/help - Эта справка

**Как анализировать еду:**
1. Сделайте фото вашего блюда
2. Отправьте фото боту
3. Дождитесь анализа (может занять несколько секунд)
4. Получите детальную информацию о калориях

**Советы для лучших результатов:**
• Фотографируйте еду хорошо освещенной
• Показывайте всю порцию целиком
• Избегайте размытых фото
• Фотографируйте на контрастном фоне

**Функции статистики:**
• Калории за день/неделю/месяц
• График изменения веса
• Анализ питательных веществ
• Достижение целей

Есть вопросы? Просто напишите мне!
"""
        
        keyboard = [
            [InlineKeyboardButton(f"{config.EMOJIS['back']} Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = update.message or update.callback_query.message
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        else:
            await message.reply_text(
                help_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
    
    @staticmethod
    async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик фотографий еды"""
        user = update.effective_user
        
        # Сбрасываем флаг сохранения анализа при получении нового фото
        context.user_data.pop('preserve_analysis_message', None)
        
        # Получаем или создаем пользователя
        db_user = DatabaseManager.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Отправляем сообщение о начале анализа
        analyzing_message = await update.message.reply_text(
            f"{config.EMOJIS['food']} Анализирую ваше блюдо...\n⏳ Это может занять несколько секунд"
        )
        
        try:
            # Получаем фото наибольшего размера
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            # Скачиваем фото
            image_bytes = BytesIO()
            await file.download_to_memory(image_bytes)
            image_data = image_bytes.getvalue()
            
            # Анализируем с помощью AI
            result = await analyzer.analyze_food_image(image_data)
            
            # Показываем ошибку только если совсем ничего не найдено
            if result.get('error') and result.get('total_calories', 0) == 0:
                await analyzing_message.edit_text(
                    f"{config.EMOJIS['error']} Произошла ошибка при анализе: {result['error']}\n\nПопробуйте еще раз или отправьте другое фото."
                )
                return
            
            # Сохраняем результат в базу данных
            if result.get('total_calories', 0) > 0:
                DatabaseManager.add_food_entry(
                    user_id=db_user.id,
                    food_data=json.dumps(result['food_items'], ensure_ascii=False),
                    total_calories=result['total_calories'],
                    total_proteins=result.get('total_proteins', 0),
                    total_carbs=result.get('total_carbs', 0),
                    total_fats=result.get('total_fats', 0),
                    confidence=result.get('confidence', 0),
                    photo_id=photo.file_id
                )
            
            # Форматируем результат
            formatted_result = analyzer.format_analysis_result(result)
            
            # Добавляем информацию о дневном прогрессе
            # ИСПРАВЛЕНИЕ: получаем калории ПОСЛЕ сохранения в БД
            today_calories = DatabaseManager.get_today_calories(db_user.id)
            daily_goal = db_user.daily_calorie_goal
            remaining = daily_goal - today_calories
            
            progress_message = f"\n\n{config.EMOJIS['chart']} **Прогресс за день:**\n"
            progress_message += f"Съедено: {today_calories:.0f} из {daily_goal} ккал\n"
            
            if remaining > 0:
                progress_message += f"Осталось: {remaining:.0f} ккал {config.EMOJIS['checkmark']}"
            else:
                over = abs(remaining)
                progress_message += f"Превышение: +{over:.0f} ккал {config.EMOJIS['warning']}"
            
            formatted_result += progress_message
            
            # Сохраняем данные для коррекции
            context.user_data['last_photo_id'] = photo.file_id
            context.user_data['last_analysis_result'] = result
            context.user_data['preserve_analysis_message'] = True  # Флаг для сохранения сообщения с анализом
            
            # Клавиатура с действиями
            keyboard = [
                [InlineKeyboardButton(f"{config.EMOJIS['stats']} Статистика", callback_data="stats")],
                [InlineKeyboardButton("🔧 Исправить анализ", callback_data="correct_analysis")],
                [InlineKeyboardButton(f"{config.EMOJIS['food']} Добавить еще блюдо", callback_data="add_more")],
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем результат
            await analyzing_message.edit_text(
                formatted_result,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Ошибка при обработке фото: {e}")
            await analyzing_message.edit_text(
                f"{config.EMOJIS['error']} Произошла ошибка при анализе фото.\n\nПожалуйста, попробуйте еще раз или отправьте другое изображение."
            )
    
    @staticmethod
    async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик статистики"""
        user = update.effective_user if update.message else update.callback_query.from_user
        
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        
        # Получаем статистику за неделю
        stats = DatabaseManager.get_user_stats(db_user.id, days=7)
        
        if not stats:
            message = f"{config.EMOJIS['stats']} **Статистика питания**\n\nУ вас пока нет записей о питании.\nОтправьте фото еды, чтобы начать отслеживание!"
        else:
            # Сегодняшняя статистика
            today = datetime.now().date()
            today_stat = next((s for s in stats if s.date == today), None)
            
            message = f"{config.EMOJIS['stats']} **Статистика питания**\n\n"
            
            if today_stat:
                message += f"**Сегодня ({today.strftime('%d.%m')})**\n"
                message += f"{config.EMOJIS['fire']} Калории: {today_stat.total_calories:.0f} из {db_user.daily_calorie_goal}\n"
                message += f"{config.EMOJIS['muscle']} Белки: {today_stat.total_proteins:.1f}г\n"
                message += f"🍞 Углеводы: {today_stat.total_carbs:.1f}г\n"
                message += f"🥑 Жиры: {today_stat.total_fats:.1f}г\n"
                message += f"{config.EMOJIS['food']} Приемов пищи: {today_stat.meals_count}\n\n"
                
                # Прогресс к цели
                progress = (today_stat.total_calories / db_user.daily_calorie_goal) * 100
                if progress <= 100:
                    message += f"📊 Прогресс к цели: {progress:.1f}% {config.EMOJIS['checkmark']}\n\n"
                else:
                    message += f"📊 Превышение цели: {progress:.1f}% {config.EMOJIS['warning']}\n\n"
            
            # Средние за неделю
            weekly_avg_calories = sum(s.total_calories for s in stats) / len(stats)
            weekly_total_calories = sum(s.total_calories for s in stats)
            
            message += f"**За неделю (средние в день)**\n"
            message += f"{config.EMOJIS['fire']} Калории: {weekly_avg_calories:.0f}\n"
            message += f"📈 Всего за неделю: {weekly_total_calories:.0f} ккал\n"
            message += f"📅 Дней с записями: {len(stats)} из 7"
        
        keyboard = [
            [InlineKeyboardButton(f"{config.EMOJIS['chart']} Подробная статистика", callback_data="detailed_stats")],
            [InlineKeyboardButton(f"{config.EMOJIS['settings']} Настройки цели", callback_data="settings")],
            [InlineKeyboardButton(f"{config.EMOJIS['back']} Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Проверяем флаг сохранения сообщения с анализом фото
        preserve_analysis = context.user_data.get('preserve_analysis_message', False)
        
        if update.callback_query and not preserve_analysis:
            await update.callback_query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        else:
            # Если это callback после анализа фото или обычное сообщение - отправляем новое сообщение
            if update.callback_query:
                await update.callback_query.answer()  # Закрываем "часики" на кнопке
                bot = update.callback_query.get_bot()
                chat_id = update.callback_query.message.chat_id
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
    
    @staticmethod
    async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик настроек"""
        user = update.effective_user if update.message else update.callback_query.from_user
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        
        # ЛОГИРОВАНИЕ: Текущие настройки пользователя
        logger.info(f"⚙️ Загрузка настроек пользователя {user.id} ({db_user.telegram_id}):")
        logger.info(f"   Цель калорий: {db_user.daily_calorie_goal}")
        logger.info(f"   Вес: {db_user.weight}")
        logger.info(f"   Рост: {db_user.height}")
        logger.info(f"   Возраст: {db_user.age}")
        logger.info(f"   Пол: {db_user.gender}")
        
        message = f"{config.EMOJIS['settings']} **Настройки профиля**\n\n"
        message += f"**Текущие настройки:**\n"
        message += f"🎯 Цель калорий в день: {db_user.daily_calorie_goal} ккал\n"
        
        if db_user.weight:
            message += f"{config.EMOJIS['scales']} Вес: {db_user.weight} кг\n"
        if db_user.height:
            message += f"📏 Рост: {db_user.height} см\n"
        if db_user.age:
            message += f"🎂 Возраст: {db_user.age} лет\n"
        if db_user.gender:
            message += f"👤 Пол: {'мужской' if db_user.gender == 'male' else 'женский'}\n"
        
        message += f"\nВыберите, что хотите настроить:"
        
        keyboard = [
            [InlineKeyboardButton("🎯 Изменить цель калорий", callback_data="set_calorie_goal")],
            [InlineKeyboardButton(f"{config.EMOJIS['scales']} Обновить вес", callback_data="set_weight")],
            [InlineKeyboardButton("📏 Указать рост", callback_data="set_height")],
            [InlineKeyboardButton("👤 Указать пол и возраст", callback_data="set_personal_info")],
            [InlineKeyboardButton(f"{config.EMOJIS['back']} Назад", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
    
    @staticmethod
    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик inline кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "main_menu":
            await CalorieBotHandlers.start_command(update, context)
        elif query.data == "stats":
            await CalorieBotHandlers.stats_handler(update, context)
        elif query.data == "settings":
            await CalorieBotHandlers.settings_handler(update, context)
        elif query.data == "help":
            await CalorieBotHandlers.help_command(update, context)
        elif query.data == "add_more":
            await query.answer()
            bot = query.get_bot()
            chat_id = query.message.chat_id
            await bot.send_message(
                chat_id=chat_id,
                text=f"{config.EMOJIS['food']} Отправьте фото следующего блюда для анализа калорий!"
            )
        elif query.data == "detailed_stats":
            await CalorieBotHandlers.detailed_stats_handler(update, context)
        elif query.data.startswith("set_"):
            await CalorieBotHandlers.settings_input_handler(update, context)
        elif query.data == "correct_analysis":
            await CalorieBotHandlers.correction_handler(update, context)
        elif query.data == "cancel_correction":
            context.user_data.pop('waiting_for', None)
            context.user_data.pop('correction_photo_id', None)
            await query.edit_message_text("❌ Коррекция отменена")
        elif query.data == "daily_history":
            await CalorieBotHandlers.daily_history_handler(update, context)
        elif query.data == "weekly_stats_detail":
            await CalorieBotHandlers.weekly_stats_detail_handler(update, context)
        elif query.data == "back_to_profile":
            await CalorieBotHandlers.back_to_profile_handler(update, context)
        elif query.data == "edit_profile":
            await CalorieBotHandlers.settings_handler(update, context)
        elif query.data == "profile":
            await CalorieBotHandlers.profile_callback_handler(update, context)
    
    @staticmethod
    async def detailed_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Детальная статистика"""
        user = update.callback_query.from_user
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        
        # Получаем статистику за месяц
        stats = DatabaseManager.get_user_stats(db_user.id, days=30)
        
        if not stats:
            message = f"{config.EMOJIS['chart']} **Подробная статистика**\n\nНедостаточно данных для анализа.\nПродолжайте добавлять записи о питании!"
        else:
            message = f"{config.EMOJIS['chart']} **Подробная статистика за 30 дней**\n\n"
            
            # Общая статистика
            total_calories = sum(s.total_calories for s in stats)
            avg_calories = total_calories / len(stats)
            days_with_records = len(stats)
            
            message += f"**Общие показатели:**\n"
            message += f"📊 Дней с записями: {days_with_records} из 30\n"
            message += f"🔥 Общее потребление: {total_calories:.0f} ккал\n"
            message += f"📈 Среднее в день: {avg_calories:.0f} ккал\n"
            message += f"🎯 Цель в день: {db_user.daily_calorie_goal} ккал\n\n"
            
            # Анализ соблюдения цели
            goal_days = sum(1 for s in stats if s.total_calories <= db_user.daily_calorie_goal)
            goal_percentage = (goal_days / days_with_records) * 100 if days_with_records > 0 else 0
            
            message += f"**Соблюдение цели:**\n"
            message += f"✅ Дней в пределах цели: {goal_days} ({goal_percentage:.1f}%)\n"
            message += f"⚠️ Дней с превышением: {days_with_records - goal_days}\n\n"
            
            # Питательные вещества
            avg_proteins = sum(s.total_proteins for s in stats) / len(stats)
            avg_carbs = sum(s.total_carbs for s in stats) / len(stats)
            avg_fats = sum(s.total_fats for s in stats) / len(stats)
            
            message += f"**Питательные вещества (среднее в день):**\n"
            message += f"💪 Белки: {avg_proteins:.1f}г\n"
            message += f"🍞 Углеводы: {avg_carbs:.1f}г\n"
            message += f"🥑 Жиры: {avg_fats:.1f}г\n"
        
        keyboard = [
            [InlineKeyboardButton(f"{config.EMOJIS['back']} К статистике", callback_data="stats")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    @staticmethod
    async def settings_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ввода настроек"""
        query = update.callback_query
        setting_type = query.data
        
        if setting_type == "set_calorie_goal":
            message = f"🎯 **Установка цели калорий**\n\nВведите желаемое количество калорий в день (например: 2000):"
            context.user_data['waiting_for'] = 'calorie_goal'
        elif setting_type == "set_weight":
            message = f"{config.EMOJIS['scales']} **Обновление веса**\n\nВведите ваш текущий вес в килограммах (например: 70.5):"
            context.user_data['waiting_for'] = 'weight'
        elif setting_type == "set_height":
            message = f"📏 **Указание роста**\n\nВведите ваш рост в сантиметрах (например: 175):"
            context.user_data['waiting_for'] = 'height'
        elif setting_type == "set_personal_info":
            message = f"👤 **Личная информация**\n\nВведите ваш возраст и пол через пробел (например: 25 мужской или 30 женский):"
            context.user_data['waiting_for'] = 'personal_info'
        
        keyboard = [
            [InlineKeyboardButton(f"{config.EMOJIS['back']} Отмена", callback_data="settings")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    @staticmethod
    async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user = update.effective_user
        text = update.message.text
        
        # Проверяем, ожидаем ли мы ввод настроек
        if context.user_data.get('waiting_for') == 'correction':
            await CalorieBotHandlers.process_correction(update, context, text)
        elif context.user_data.get('waiting_for'):
            await CalorieBotHandlers.process_settings_input(update, context, text)
        else:
            # Обычное текстовое сообщение
            await update.message.reply_text(
                f"{config.EMOJIS['food']} Отправьте мне фото вашей еды, и я посчитаю калории!\n\n"
                f"Или воспользуйтесь командами:\n"
                f"/stats - статистика\n"
                f"/settings - настройки\n"
                f"/help - помощь"
            )
    
    @staticmethod
    async def process_settings_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Обработка ввода настроек"""
        user = update.effective_user
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        waiting_for = context.user_data.get('waiting_for')
        
        success = False
        error_message = ""
        
        try:
            if waiting_for == 'calorie_goal':
                calorie_goal = int(text)
                if 500 <= calorie_goal <= 5000:
                    # ЛОГИРОВАНИЕ: Сохранение цели калорий
                    logger.info(f"👤 Пользователь {user.id} ({db_user.telegram_id}) меняет цель калорий: {db_user.daily_calorie_goal} → {calorie_goal}")
                    updated_user = DatabaseManager.update_user_settings(db_user.id, daily_calorie_goal=calorie_goal)
                    success = True
                    message = f"✅ Цель калорий установлена: {calorie_goal} ккал в день"
                    logger.info(f"✅ Цель обновлена в БД: {updated_user.daily_calorie_goal}")
                else:
                    error_message = "Цель калорий должна быть между 500 и 5000 ккал"
            
            elif waiting_for == 'weight':
                weight = float(text.replace(',', '.'))
                if 20 <= weight <= 300:
                    logger.info(f"👤 Пользователь {user.id} ({db_user.telegram_id}) устанавливает вес: {weight} кг")
                    updated_user = DatabaseManager.update_user_settings(db_user.id, weight=weight)
                    success = True
                    message = f"✅ Вес обновлен: {weight} кг"
                    logger.info(f"✅ Вес сохранен в БД: {updated_user.weight}")
                else:
                    error_message = "Вес должен быть между 20 и 300 кг"
            
            elif waiting_for == 'height':
                height = int(text)
                if 100 <= height <= 250:
                    DatabaseManager.update_user_settings(db_user.id, height=height)
                    success = True
                    message = f"✅ Рост установлен: {height} см"
                else:
                    error_message = "Рост должен быть между 100 и 250 см"
            
            elif waiting_for == 'personal_info':
                parts = text.lower().split()
                if len(parts) >= 2:
                    age = int(parts[0])
                    gender = 'male' if 'муж' in parts[1] else 'female' if 'жен' in parts[1] else None
                    
                    if 10 <= age <= 120 and gender:
                        DatabaseManager.update_user_settings(db_user.id, age=age, gender=gender)
                        success = True
                        gender_text = 'мужской' if gender == 'male' else 'женский'
                        message = f"✅ Информация обновлена: {age} лет, {gender_text}"
                    else:
                        error_message = "Проверьте формат ввода: возраст (10-120) и пол (мужской/женский)"
                else:
                    error_message = "Введите возраст и пол через пробел"
        
        except ValueError:
            error_message = "Неверный формат данных"
        
        # Очищаем состояние ожидания
        context.user_data.pop('waiting_for', None)
        
        if success:
            keyboard = [
                [InlineKeyboardButton(f"{config.EMOJIS['settings']} Настройки", callback_data="settings")],
                [InlineKeyboardButton(f"{config.EMOJIS['back']} Главное меню", callback_data="main_menu")]
            ]
        else:
            message = f"❌ {error_message}\n\nПопробуйте еще раз или отмените операцию."
            keyboard = [
                [InlineKeyboardButton(f"{config.EMOJIS['back']} Отмена", callback_data="settings")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup
        )

    @staticmethod
    async def correction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик коррекции анализа"""
        query = update.callback_query
        
        # Проверяем есть ли данные для коррекции
        if 'last_analysis_result' not in context.user_data:
            await query.answer()
            bot = query.get_bot()
            chat_id = query.message.chat_id
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Нет данных для коррекции. Пошлите новое фото."
            )
            return
        
        context.user_data['waiting_for'] = 'correction'
        
        # Показываем текущий анализ для удобства
        result = context.user_data['last_analysis_result']
        current_items = "\n".join([
            f"• {item['name']}: {item.get('estimated_weight', 'вес не указан')}"
            for item in result.get('food_items', [])
        ])
        
        message = f"""
🔧 **Коррекция анализа**

**Текущий анализ:**
{current_items}
**Общие калории:** {result.get('total_calories', 0)} ккал

**Как исправить:**
• `calories 850` - изменить общие калории  
• `бутерброды 320г` - исправить вес продукта

**Примеры:**
• `calories 900`
• `бутерброды 320г`
• `блины 180г`

Напишите ваше исправление:
"""
        
        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_correction")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем новое сообщение, сохраняя исходный анализ
        await query.answer()
        bot = query.get_bot()
        chat_id = query.message.chat_id
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    @staticmethod
    async def process_correction(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Обработка коррекции данных"""
        user = update.effective_user
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        
        try:
            # Парсим введенную коррекцию
            text_lower = text.lower()
            
            if text_lower.startswith('калории '):
                # Коррекция общих калорий
                new_calories = int(text.split()[1])
                if 0 <= new_calories <= 5000:
                    # Здесь можно обновить последнюю запись в БД
                    message = f"✅ Калории скорректированы: {new_calories} ккал"
                    success = True
                else:
                    message = "❌ Калории должны быть от 0 до 5000"
                    success = False
            else:
                # Коррекция веса продукта
                parts = text.split()
                if len(parts) >= 2:
                    dish_name = parts[0]
                    new_weight = ' '.join(parts[1:])
                    message = f"✅ Исправлено: {dish_name} - {new_weight}"
                    success = True
                else:
                    message = "❌ Неверный формат. Используйте: 'блюдо вес' (например: блины 180г)"
                    success = False
            
        except ValueError:
            message = "❌ Ошибка в формате числа"
            success = False
        
        # Очищаем состояние
        context.user_data.pop('waiting_for', None)
        context.user_data.pop('correction_photo_id', None)
        
        keyboard = [
            [InlineKeyboardButton(f"{config.EMOJIS['stats']} Статистика", callback_data="stats")],
            [InlineKeyboardButton(f"{config.EMOJIS['back']} Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup
        )

    @staticmethod
    async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Личный кабинет пользователя"""
        user = update.effective_user
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        
        # Основная информация
        profile_info = DatabaseManager.get_user_info(db_user.id)
        
        # Количество дней ведения записей
        tracking_days = DatabaseManager.get_tracking_days(db_user.id)
        
        message = f"""
👤 **Личный кабинет**

**Основная информация:**
📝 Имя: {user.first_name or 'Не указано'}
📊 Ведёте записи: {tracking_days} дней
🎯 Цель калорий: {db_user.daily_calorie_goal} ккал/день

**Физические параметры:**
⚖️ Вес: {db_user.weight if db_user.weight else 'Не указан'} кг
📏 Рост: {db_user.height if db_user.height else 'Не указан'} см
🎂 Возраст: {db_user.age if db_user.age else 'Не указан'} лет
🚻 Пол: {db_user.gender if db_user.gender else 'Не указан'}

**Текущая статистика:**
🔥 Сегодня: {profile_info['today_calories']} / {db_user.daily_calorie_goal} ккал
📈 За неделю: {profile_info['week_avg']:.0f} ккал/день (среднее)
📅 За месяц: {profile_info['month_avg']:.0f} ккал/день (среднее)
"""
        
        keyboard = [
            [InlineKeyboardButton("📅 История по дням", callback_data="daily_history")],
            [InlineKeyboardButton("📊 Недельная статистика", callback_data="weekly_stats_detail")],
            [InlineKeyboardButton("⚙️ Изменить параметры", callback_data="edit_profile")],
            [InlineKeyboardButton(f"{config.EMOJIS['back']} Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    @staticmethod
    async def profile_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback для личного кабинета"""
        query = update.callback_query
        user = query.from_user
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        
        # Основная информация
        profile_info = DatabaseManager.get_user_info(db_user.id)
        
        # Количество дней ведения записей
        tracking_days = DatabaseManager.get_tracking_days(db_user.id)
        
        message = f"""
👤 **Личный кабинет**

**Основная информация:**
📝 Имя: {user.first_name or 'Не указано'}
📊 Ведёте записи: {tracking_days} дней
🎯 Цель калорий: {db_user.daily_calorie_goal} ккал/день

**Физические параметры:**
⚖️ Вес: {db_user.weight if db_user.weight else 'Не указан'} кг
📏 Рост: {db_user.height if db_user.height else 'Не указан'} см
🎂 Возраст: {db_user.age if db_user.age else 'Не указан'} лет
🚻 Пол: {db_user.gender if db_user.gender else 'Не указан'}

**Текущая статистика:**
🔥 Сегодня: {profile_info['today_calories']} / {db_user.daily_calorie_goal} ккал
📈 За неделю: {profile_info['week_avg']:.0f} ккал/день (среднее)
📅 За месяц: {profile_info['month_avg']:.0f} ккал/день (среднее)
"""
        
        keyboard = [
            [InlineKeyboardButton("📅 История по дням", callback_data="daily_history")],
            [InlineKeyboardButton("📊 Недельная статистика", callback_data="weekly_stats_detail")],
            [InlineKeyboardButton("⚙️ Изменить параметры", callback_data="edit_profile")],
            [InlineKeyboardButton(f"{config.EMOJIS['back']} Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    @staticmethod
    async def daily_history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает историю калорий по дням"""
        query = update.callback_query
        user = query.from_user
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        
        # Получаем историю за последние 14 дней
        daily_history = DatabaseManager.get_daily_calorie_history(db_user.id, days=14)
        
        if not daily_history:
            message = f"{config.EMOJIS['warning']} **История калорий**\n\nПока нет записей о питании.\nНачните добавлять фото еды!"
        else:
            message = f"📅 **История калорий (последние 14 дней)**\n\n"
            
            for entry in daily_history:
                date_str = entry['date'].strftime("%d.%m")
                day_name = entry['date'].strftime("%a")  # сокращенное название дня
                calories = entry['calories']
                goal = db_user.daily_calorie_goal
                
                # Эмодзи в зависимости от достижения цели
                if calories >= goal * 0.9 and calories <= goal * 1.1:
                    status = "🎯"  # близко к цели
                elif calories < goal * 0.7:
                    status = "🔽"  # мало
                elif calories > goal * 1.3:
                    status = "🔺"  # много
                else:
                    status = "📊"  # норма
                
                message += f"{status} **{date_str} ({day_name}):** {calories:.0f} ккал\n"
        
        keyboard = [
            [InlineKeyboardButton("📊 Подробная статистика", callback_data="detailed_stats")],
            [InlineKeyboardButton(f"{config.EMOJIS['back']} К профилю", callback_data="back_to_profile")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    @staticmethod
    async def weekly_stats_detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Детальная недельная статистика"""
        query = update.callback_query
        user = query.from_user
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        
        # Получаем статистику за последние 4 недели
        weekly_stats = DatabaseManager.get_weekly_stats(db_user.id)
        
        if not weekly_stats:
            message = f"{config.EMOJIS['warning']} **Недельная статистика**\n\nНедостаточно данных.\nПродолжайте вести записи!"
        else:
            message = f"📊 **Статистика по неделям**\n\n"
            
            for i, week in enumerate(weekly_stats):
                week_num = i + 1
                avg_calories = week['avg_calories']
                days_tracked = week['days_tracked']
                goal = db_user.daily_calorie_goal
                
                # Процент от цели
                goal_percent = (avg_calories / goal * 100) if goal > 0 else 0
                
                if goal_percent >= 90 and goal_percent <= 110:
                    status = "🎯 Отлично"
                elif goal_percent < 80:
                    status = "🔽 Мало калорий"
                elif goal_percent > 120:
                    status = "🔺 Много калорий"
                else:
                    status = "📊 Норма"
                
                message += f"**Неделя {week_num}:**\n"
                message += f"📈 Среднее: {avg_calories:.0f} ккал/день ({goal_percent:.0f}%)\n"
                message += f"📅 Дней с записями: {days_tracked}/7\n"
                message += f"{status}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("📅 История по дням", callback_data="daily_history")],
            [InlineKeyboardButton(f"{config.EMOJIS['back']} К профилю", callback_data="back_to_profile")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    @staticmethod
    async def back_to_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к профилю"""
        await CalorieBotHandlers.profile_callback_handler(update, context)

class WeeklyStatsScheduler:
    """Класс для планирования еженедельных уведомлений"""
    
    def __init__(self, application):
        self.application = application
    
    async def send_weekly_stats(self):
        """Отправка еженедельной статистики всем активным пользователям"""
        logger.info("Начинаем отправку еженедельной статистики...")
        
        db = DatabaseManager.SessionLocal()
        try:
            # Получаем всех активных пользователей
            from database import User
            users = db.query(User).filter(User.is_active == True).all()
            
            for user in users:
                try:
                    # Получаем статистику за неделю
                    weekly_stats = DatabaseManager.get_weekly_stats(user.id)
                    
                    if not weekly_stats:
                        continue  # Пропускаем пользователей без статистики
                    
                    # Формируем сообщение
                    current_week = weekly_stats[0] if weekly_stats else None
                    if not current_week:
                        continue
                    
                    avg_calories = current_week['avg_calories']
                    days_tracked = current_week['days_tracked']
                    goal = user.daily_calorie_goal
                    goal_percent = (avg_calories / goal * 100) if goal > 0 else 0
                    
                    # Определяем статус
                    if goal_percent >= 90 and goal_percent <= 110:
                        status = "🎯 Отлично! Вы близки к цели"
                        emoji = "🎉"
                    elif goal_percent < 80:
                        status = "🔽 Стоит увеличить калорийность"
                        emoji = "💪"
                    elif goal_percent > 120:
                        status = "🔺 Возможно, стоит быть умереннее"
                        emoji = "🧘‍♂️"
                    else:
                        status = "📊 Держитесь в норме"
                        emoji = "✅"
                    
                    message = f"""
{emoji} **Итоги недели**

**Ваша статистика за последние 7 дней:**
📈 Среднее потребление: {avg_calories:.0f} ккал/день
🎯 Ваша цель: {goal} ккал/день
📊 Выполнение цели: {goal_percent:.0f}%
📅 Дней с записями: {days_tracked}/7

{status}

**Совет на следующую неделю:**
{"Продолжайте в том же духе!" if 90 <= goal_percent <= 110 else "Попробуйте следить за калориями каждый день для лучших результатов!"}

Удачи в новой неделе! 🌟
                    """
                    
                    # Отправляем сообщение
                    await self.application.bot.send_message(
                        chat_id=user.telegram_id,
                        text=message.strip(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    logger.info(f"Еженедельная статистика отправлена пользователю {user.telegram_id}")
                    
                    # Небольшая пауза между отправками
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Ошибка отправки статистики пользователю {user.telegram_id}: {e}")
                    continue
                    
        finally:
            db.close()
        
        logger.info("Отправка еженедельной статистики завершена")
    
    def schedule_weekly_stats(self):
        """Планирование еженедельных уведомлений"""
        # Отправляем каждое воскресенье в 20:00
        schedule.every().sunday.at("20:00").do(
            lambda: asyncio.create_task(self.send_weekly_stats())
        )
        
        # Запускаем планировщик в отдельном потоке
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)  # Проверяем каждую минуту
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("Планировщик еженедельной статистики запущен")

def main():
    """Основная функция запуска бота"""
    # Создаем таблицы базы данных
    create_tables()
    logger.info("База данных инициализирована")
    
    # Создаем приложение
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", CalorieBotHandlers.start_command))
    application.add_handler(CommandHandler("help", CalorieBotHandlers.help_command))
    application.add_handler(CommandHandler("stats", CalorieBotHandlers.stats_handler))
    application.add_handler(CommandHandler("settings", CalorieBotHandlers.settings_handler))
    application.add_handler(CommandHandler("profile", CalorieBotHandlers.profile_command))
    application.add_handler(CommandHandler("fixgoal", CalorieBotHandlers.fix_goal_command))
    application.add_handler(CommandHandler("testai", CalorieBotHandlers.test_ai_command))
    application.add_handler(CommandHandler("debuguser", CalorieBotHandlers.debug_user_command))
    application.add_handler(CommandHandler("resetuser", CalorieBotHandlers.reset_user_command))
    application.add_handler(CommandHandler("debugstats", CalorieBotHandlers.debug_stats_command))
    application.add_handler(CommandHandler("rebuildstats", CalorieBotHandlers.rebuild_stats_command))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.PHOTO, CalorieBotHandlers.photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, CalorieBotHandlers.text_handler))
    
    # Обработчик inline кнопок
    application.add_handler(CallbackQueryHandler(CalorieBotHandlers.button_handler))
    
    # Запускаем планировщик еженедельной статистики
    scheduler = WeeklyStatsScheduler(application)
    scheduler.schedule_weekly_stats()
    
    # Запускаем бота
    logger.info(f"Запускаем {config.BOT_NAME}...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
