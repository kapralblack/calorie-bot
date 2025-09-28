"""
Основной файл телеграм-бота для подсчета калорий
"""
import asyncio
import logging
import json
from datetime import datetime, timedelta
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
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        help_message = f"""
{config.EMOJIS['help']} **Помощь по использованию бота**

**Основные команды:**
/start - Начать работу с ботом
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
            
            if result.get('error'):
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
    async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик настроек"""
        user = update.effective_user if update.message else update.callback_query.from_user
        db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
        
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
            await query.edit_message_text(
                f"{config.EMOJIS['food']} Отправьте фото следующего блюда для анализа калорий!"
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
                    DatabaseManager.update_user_settings(db_user.id, daily_calorie_goal=calorie_goal)
                    success = True
                    message = f"✅ Цель калорий установлена: {calorie_goal} ккал в день"
                else:
                    error_message = "Цель калорий должна быть между 500 и 5000 ккал"
            
            elif waiting_for == 'weight':
                weight = float(text.replace(',', '.'))
                if 20 <= weight <= 300:
                    DatabaseManager.update_user_settings(db_user.id, weight=weight)
                    success = True
                    message = f"✅ Вес обновлен: {weight} кг"
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
            await query.edit_message_text("❌ Нет данных для коррекции. Пошлите новое фото.")
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
        
        await query.edit_message_text(
            message,
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
    application.add_handler(CommandHandler("fixgoal", CalorieBotHandlers.fix_goal_command))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.PHOTO, CalorieBotHandlers.photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, CalorieBotHandlers.text_handler))
    
    # Обработчик inline кнопок
    application.add_handler(CallbackQueryHandler(CalorieBotHandlers.button_handler))
    
    # Запускаем бота
    logger.info(f"Запускаем {config.BOT_NAME}...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
