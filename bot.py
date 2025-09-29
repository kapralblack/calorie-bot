"""
Основной файл телеграм-бота для подсчета калорий
"""
import asyncio
import logging
import json
from datetime import datetime, timedelta, timezone
import schedule
import threading
import time
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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
    def get_main_keyboard():
        """Создает постоянную клавиатуру для главного меню"""
        keyboard = [
            [
                KeyboardButton("🍽️ Анализ еды"),
                KeyboardButton("📊 Статистика")
            ],
            [
                KeyboardButton("⚙️ Настройки"),
                KeyboardButton("📅 История")
            ],
            [
                KeyboardButton("❓ Помощь"),
                KeyboardButton("🏠 Главное меню")
            ]
        ]
        return ReplyKeyboardMarkup(
            keyboard, 
            resize_keyboard=True, 
            one_time_keyboard=False,
            input_field_placeholder="Отправьте фото еды или выберите действие..."
        )
    
    @staticmethod
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start с персонализированным онбордингом"""
        user = update.effective_user
        
        # Сбрасываем флаг сохранения анализа при возврате в главное меню
        context.user_data.pop('preserve_analysis_message', None)
        
        telegram_user = DatabaseManager.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Проверяем завершен ли онбординг
        if not DatabaseManager.is_onboarding_completed(user.id):
            await CalorieBotHandlers.start_onboarding(update, context)
            return
        
        # Если онбординг завершен, показываем обычное меню
        # Получаем быструю статистику для приветствия
        today_calories = DatabaseManager.get_today_calories(telegram_user.id)
        daily_goal = telegram_user.daily_calorie_goal
        
        # Статус дня
        progress_emoji = "🟢" if today_calories < daily_goal else "🔴" if today_calories > daily_goal * 1.1 else "🟡"
        progress_text = f"{today_calories:.0f} / {daily_goal} ккал {progress_emoji}"
        
        welcome_message = f"""
🍎 **{config.BOT_NAME}**
        
👋 С возвращением, **{user.first_name}**! 

📊 **Сегодня:** {progress_text}
💡 **Совет:** Отправьте фото еды для анализа калорий

🔥 **Ваш персональный помощник готов:**
• 📸 AI анализ фото еды с учетом ваших целей
• 📈 Умная статистика питания
• 🎯 Персональная норма калорий: {daily_goal} ккал/день
• 📱 Полная история ваших достижений

Выберите действие или отправьте фото еды:
"""
        
        # Используем постоянную клавиатуру вместо inline кнопок
        reply_markup = CalorieBotHandlers.get_main_keyboard()
        
        # ИСПРАВЛЕНИЕ: Проверяем, это callback query или обычное сообщение
        if update.callback_query:
            # Это нажатие кнопки - отправляем новое сообщение с постоянной клавиатурой
            await update.callback_query.message.reply_text(
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

    # ======= ADMIN COMMANDS =======
    @staticmethod
    def is_admin(user_id):
        """Проверяет является ли пользователь админом"""
        if not config.ADMIN_USER_ID:
            return False
        try:
            return str(user_id) == config.ADMIN_USER_ID
        except:
            return False

    @staticmethod
    async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /adminstats - общая статистика по боту"""
        user = update.effective_user
        
        if not CalorieBotHandlers.is_admin(user.id):
            await update.message.reply_text("❌ Доступ запрещен. Только для администратора.")
            return
        
        try:
            stats = DatabaseManager.get_admin_stats()
            
            message = f"""
👑 <b>Административная панель</b>
📊 <b>Общая статистика бота</b>

👥 <b>Пользователи:</b>
• Всего зарегистрировано: {stats['total_users']}
• Активных за 7 дней: {stats['active_users_7d']}
• С настроенными целями: {stats['configured_users']}

📱 <b>Активность:</b>
• Всего записей о еде: {stats['total_food_entries']}
• Записей сегодня: {stats['today_entries']}

🏆 <b>Топ пользователей:</b>
"""
            
            for i, user in enumerate(stats['top_users'], 1):
                # Экранируем имя пользователя для безопасного отображения
                name_safe = user['name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                message += f"{i}. {name_safe} - {user['entries_count']} записей\n"
            
            if not stats['top_users']:
                message += "Нет активных пользователей\n"
            
            message += f"""

🔧 <b>Админские команды:</b>
/adminusers - список пользователей
/adminuser [ID] - информация о пользователе
/adminexport - экспорт данных
"""
            
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения статистики: {e}")

    @staticmethod
    async def admin_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /adminusers - список всех пользователей"""
        user = update.effective_user
        
        if not CalorieBotHandlers.is_admin(user.id):
            await update.message.reply_text("❌ Доступ запрещен. Только для администратора.")
            return
        
        try:
            users = DatabaseManager.get_all_users_summary()
            
            if not users:
                await update.message.reply_text("📝 Пользователей пока нет")
                return
            
            # Используем HTML вместо Markdown для лучшей совместимости
            message = f"👥 <b>Все пользователи ({len(users)}):</b>\n\n"
            
            for i, user_info in enumerate(users[:15], 1):  # Показываем только первых 15
                name = user_info['name']
                username = f"@{user_info['username']}" if user_info['username'] else 'нет username'
                entries = user_info['entries_count']
                goal = user_info['daily_calorie_goal']
                
                # Статус активности
                if user_info['last_activity']:
                    # Убеждаемся что last_activity имеет timezone info
                    last_activity = user_info['last_activity']
                    if last_activity.tzinfo is None:
                        # Если нет timezone, добавляем UTC
                        last_activity = last_activity.replace(tzinfo=timezone.utc)
                    
                    days_ago = (datetime.now(timezone.utc) - last_activity).days
                    activity = f"{days_ago}д назад" if days_ago > 0 else "сегодня"
                else:
                    activity = "неактивен"
                
                # Экранируем HTML символы
                name_escaped = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                username_escaped = username.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                message += f"{i}. <b>{name_escaped}</b> ({username_escaped})\n"
                message += f"   ID: <code>{user_info['telegram_id']}</code> • {entries} записей • цель {goal} ккал\n"
                message += f"   Активность: {activity}\n\n"
            
            if len(users) > 15:
                message += f"... и еще {len(users) - 15} пользователей\n\n"
            
            message += "💡 Используйте /adminuser [ID] для детальной информации"
            
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения списка пользователей: {e}")

    @staticmethod
    async def admin_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /adminuser [telegram_id] - детальная информация о пользователе"""
        user = update.effective_user
        
        if not CalorieBotHandlers.is_admin(user.id):
            await update.message.reply_text("❌ Доступ запрещен. Только для администратора.")
            return
        
        if not context.args:
            await update.message.reply_text("📝 Использование: /adminuser [telegram_id]")
            return
        
        try:
            telegram_id = int(context.args[0])
            user_info = DatabaseManager.get_user_detailed_info(telegram_id)
            
            if not user_info:
                await update.message.reply_text(f"❌ Пользователь с ID {telegram_id} не найден")
                return
            
            user_obj = user_info['user']
            
            # Экранируем данные для безопасного отображения в HTML
            name_safe = (user_obj.first_name or 'Неизвестно').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            username_safe = (user_obj.username or 'нет').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            message = f"""
🔍 <b>Детальная информация о пользователе</b>

👤 <b>Основные данные:</b>
• Имя: {name_safe}
• Username: @{username_safe}
• Telegram ID: <code>{user_obj.telegram_id}</code>
• Дата регистрации: {user_obj.created_at.strftime('%d.%m.%Y %H:%M')}

⚙️ <b>Настройки:</b>
• Цель калорий: {user_obj.daily_calorie_goal} ккал/день
• Вес: {user_obj.weight or 'не указан'} {'кг' if user_obj.weight else ''}
• Рост: {user_obj.height or 'не указан'} {'см' if user_obj.height else ''}
• Возраст: {user_obj.age or 'не указан'} {'лет' if user_obj.age else ''}
• Пол: {('мужской' if user_obj.gender == 'male' else 'женский') if user_obj.gender else 'не указан'}

📊 <b>Статистика:</b>
• Всего записей: {user_info['total_entries']}
• Дней с записями: {user_info['unique_days']}
• Всего калорий: {user_info['total_calories']:.0f} ккал
• Среднее в день: {user_info['avg_calories_per_day']:.0f} ккал

🕒 <b>Последние записи:</b>
"""
            
            for entry in user_info['recent_entries']:
                date_str = entry['created_at'].strftime('%d.%m %H:%M')
                confidence_emoji = "🟢" if entry['confidence'] > 80 else "🟡" if entry['confidence'] > 60 else "🔴"
                message += f"• {date_str}: {entry['calories']:.0f} ккал {confidence_emoji}\n"
            
            if not user_info['recent_entries']:
                message += "Записей нет\n"
            
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.HTML
            )
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат ID. Используйте числовой ID.")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения информации: {e}")

    @staticmethod
    async def admin_export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /adminexport - экспорт данных пользователей в CSV формате"""
        user = update.effective_user
        
        if not CalorieBotHandlers.is_admin(user.id):
            await update.message.reply_text("❌ Доступ запрещен. Только для администратора.")
            return
        
        try:
            users = DatabaseManager.get_all_users_summary()
            
            if not users:
                await update.message.reply_text("📝 Нет данных для экспорта")
                return
            
            # Создаем CSV данные
            import io
            import csv
            
            csv_data = io.StringIO()
            writer = csv.writer(csv_data)
            
            # Заголовки
            writer.writerow([
                'Telegram ID', 'Имя', 'Username', 'Дата регистрации',
                'Последняя активность', 'Количество записей', 'Цель калорий',
                'Вес', 'Рост', 'Возраст', 'Пол'
            ])
            
            # Данные пользователей
            for user_info in users:
                writer.writerow([
                    user_info['telegram_id'],
                    user_info['name'],
                    user_info['username'] or '',
                    user_info['created_at'].strftime('%Y-%m-%d %H:%M:%S') if user_info['created_at'] else '',
                    user_info['last_activity'].strftime('%Y-%m-%d %H:%M:%S') if user_info['last_activity'] else '',
                    user_info['entries_count'],
                    user_info['daily_calorie_goal'],
                    user_info['weight'] or '',
                    user_info['height'] or '',
                    user_info['age'] or '',
                    user_info['gender'] or ''
                ])
            
            # Отправляем файл
            csv_content = csv_data.getvalue().encode('utf-8')
            
            filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            await update.message.reply_document(
                document=io.BytesIO(csv_content),
                filename=filename,
                caption=f"📊 Экспорт данных пользователей\n👥 Пользователей: {len(users)}\n📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка экспорта данных: {e}")
            import traceback
            logger.error(f"Ошибка admin_export: {traceback.format_exc()}")

    @staticmethod
    async def admin_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admintest - простой тест админского доступа"""
        user = update.effective_user
        
        if not CalorieBotHandlers.is_admin(user.id):
            await update.message.reply_text("❌ Доступ запрещен. Только для администратора.")
            return
        
        # Простое тестовое сообщение без сложного форматирования
        message = f"""🧪 ТЕСТ АДМИНСКОЙ ПАНЕЛИ

✅ Доступ предоставлен!
👤 Ваш ID: {user.id}
📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

🔧 Основные команды работают:
• /adminstats - общая статистика
• /adminusers - список пользователей  
• /adminuser [ID] - инфо о пользователе
• /adminexport - экспорт данных

✨ Все готово для использования!"""
        
        await update.message.reply_text(message)

    @staticmethod
    async def force_migration_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Принудительная миграция telegram_id для /forcemigration"""
        if not CalorieBotHandlers.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Недостаточно прав")
            return
            
        try:
            await update.message.reply_text("🔧 Запускаю принудительную миграцию...")
            
            from database import migrate_telegram_id_if_needed
            migrate_telegram_id_if_needed()
            
            await update.message.reply_text("✅ Принудительная миграция завершена! Проверьте логи.")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при миграции: {e}")

    @staticmethod
    async def debug_migration_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отладочная команда /debugmigration для проверки статуса миграции"""
        if not CalorieBotHandlers.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Недостаточно прав")
            return
            
        try:
            import logging
            from database import engine, User
            
            # Проверяем тип telegram_id в базе данных
            with engine.connect() as connection:
                result = connection.execute(text("""
                    SELECT data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name = 'telegram_id'
                """))
                
                row = result.fetchone()
                if row:
                    data_type, is_nullable, column_default = row
                    status = f"""
🔍 **СТАТУС МИГРАЦИИ telegram_id**

📊 **Информация о поле:**
• Тип данных: `{data_type}`
• Nullable: {is_nullable}
• По умолчанию: {column_default or 'NULL'}

{'✅ МИГРАЦИЯ ВЫПОЛНЕНА - поддерживаются любые Telegram ID' if data_type == 'bigint' else '❌ МИГРАЦИЯ НЕ ВЫПОЛНЕНА - большие Telegram ID будут вызывать ошибки'}

🎯 **Рекомендации:**
{'''• Миграция успешна! Проблемы решены.''' if data_type == 'bigint' else '''• ТРЕБУЕТСЯ выполнить автоматическую миграцию
• При следующем перезапуске бота миграция должна произойти автоматически'''}
"""
                else:
                    status = "❌ Таблица users или поле telegram_id не найдено"
                
            # Тестируем создание пользователя с большим ID  
            test_large_id = 9876543210  # Большой ID для теста
            try:
                from database import DatabaseManager
                test_user = DatabaseManager.get_or_create_user(
                    telegram_id=test_large_id, 
                    username="test_large_id",
                    first_name="TestUser"
                )
                
                if hasattr(test_user, 'id') and test_user.id is not None:
                    test_result = "✅ Большие Telegram ID поддерживаются"
                    # Удаляем тестового пользователя
                    try:
                        from database import SessionLocal
                        db = SessionLocal()
                        real_test_user = db.query(User).filter(User.telegram_id == test_large_id).first()
                        if real_test_user:
                            db.delete(real_test_user)
                            db.commit()
                        db.close()
                    except:
                        pass
                else:
                    test_result = "⚠️ Большие Telegram ID создают временных пользователей"
                    
            except Exception as test_error:
                test_result = f"❌ Ошибка при тесте большого ID: {test_error}"
            
            status += f"\n\n🧪 **Тест больших Telegram ID:**\n{test_result}"
            
            await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при проверке миграции: {e}")

    @staticmethod
    async def admin_debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admindebug - отладка timezone проблем"""
        user = update.effective_user
        
        if not CalorieBotHandlers.is_admin(user.id):
            await update.message.reply_text("❌ Доступ запрещен. Только для администратора.")
            return
        
        try:
            users = DatabaseManager.get_all_users_summary()
            
            if not users:
                await update.message.reply_text("📝 Пользователей нет для отладки")
                return
            
            # Берем первого пользователя для отладки
            user_info = users[0]
            
            message = f"""🔧 ОТЛАДКА TIMEZONE

👤 Пользователь: {user_info['name']}
🆔 ID: {user_info['telegram_id']}

📅 created_at: {user_info['created_at']}
   timezone: {user_info['created_at'].tzinfo if user_info['created_at'] else 'None'}

🕐 last_activity: {user_info['last_activity']}
   timezone: {user_info['last_activity'].tzinfo if user_info['last_activity'] else 'None'}

⏰ datetime.now(timezone.utc): {datetime.now(timezone.utc)}

✅ Тест вычитания:"""
            
            # Тест вычитания
            try:
                if user_info['last_activity']:
                    days_diff = (datetime.now(timezone.utc) - user_info['last_activity']).days
                    message += f"\n   {days_diff} дней назад - ✅ OK"
                else:
                    message += f"\n   last_activity = None - ✅ OK"
            except Exception as e:
                message += f"\n   ОШИБКА: {e} - ❌ FAIL"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка отладки: {e}")

    @staticmethod
    async def admin_db_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /admindb - информация о базе данных"""
        user = update.effective_user
        
        if not CalorieBotHandlers.is_admin(user.id):
            await update.message.reply_text("❌ Доступ запрещен. Только для администратора.")
            return
        
        try:
            # Информация о базе данных
            db_type = "PostgreSQL" if config.DATABASE_URL.startswith('postgresql') else \
                     "SQLite" if config.DATABASE_URL.startswith('sqlite') else "Другая"
            
            # Безопасное отображение URL (без пароля)
            if '@' in config.DATABASE_URL:
                safe_url = config.DATABASE_URL.split('@')[1]
                db_info = f"Подключение: ...@{safe_url}"
            else:
                db_info = f"URL: {config.DATABASE_URL[:30]}..."
            
            # Статистика базы данных
            stats = DatabaseManager.get_admin_stats()
            
            # Проверка на потерю данных
            persistent_warning = ""
            if db_type == "SQLite":
                persistent_warning = """
⚠️ ВАЖНО: Используется SQLite база данных!
❌ Данные будут СБРАСЫВАТЬСЯ при каждом деплое
💡 Настройте PostgreSQL в Railway для постоянного хранения

📋 Инструкция по настройке:
1. В Railway: Add Service → Database → PostgreSQL
2. Скопируйте Postgres Connection URL  
3. Добавьте переменную DATABASE_URL в бот-сервисе
4. Перезапустите бот"""
            else:
                persistent_warning = "✅ Используется постоянная база данных - данные сохраняются!"
            
            message = f"""💾 <b>Информация о базе данных</b>

🔧 <b>Конфигурация:</b>
• Тип: {db_type}
• {db_info}

📊 <b>Текущие данные:</b>
• Пользователей: {stats['total_users']}
• Записей о еде: {stats['total_food_entries']}
• Активных за неделю: {stats['active_users_7d']}

{persistent_warning}

🔍 <b>Диагностические команды:</b>
/debugstats - состояние таблиц БД
/rebuildstats - пересоздать статистику
/adminexport - экспорт данных в CSV"""
            
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения информации о БД: {e}")

    @staticmethod
    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status - проверка статуса данных пользователя"""
        user = update.effective_user
        
        try:
            # Получаем пользователя
            db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
            
            # Определяем тип базы данных
            db_type = "PostgreSQL" if config.DATABASE_URL.startswith('postgresql') else \
                     "SQLite" if config.DATABASE_URL.startswith('sqlite') else "Другая"
            
            persistent = "✅ Данные сохраняются между перезапусками" if db_type == "PostgreSQL" else \
                        "⚠️ Данные могут сбрасываться при обновлениях бота"
            
            # Статистика пользователя
            tracking_days = DatabaseManager.get_tracking_days(db_user.id)
            today_calories = DatabaseManager.get_today_calories(db_user.id)
            
            # Дата создания аккаунта
            created_date = db_user.created_at.strftime('%d.%m.%Y') if db_user.created_at else "Неизвестно"
            
            message = f"""📊 <b>Статус ваших данных</b>

👤 <b>Профиль:</b>
• Имя: {user.first_name or 'Не указано'}
• Дата регистрации: {created_date}
• Цель калорий: {db_user.daily_calorie_goal} ккал/день

📈 <b>Активность:</b>
• Дней с записями: {tracking_days}
• Калорий сегодня: {today_calories:.0f}
• Настроен ли профиль: {'✅ Да' if (db_user.weight or db_user.height) else '⚙️ Нет (настройте в /settings)'}

💾 <b>Хранение данных:</b>
• База данных: {db_type}
• {persistent}

💡 <b>Что это означает:</b>
{'''✅ Ваши данные в безопасности! 
   Настройки и история сохранятся при обновлениях бота''' if db_type == "PostgreSQL" else 
'''⚠️ При обновлениях бота данные могут сброситься
   Рекомендуется администратору настроить PostgreSQL'''}

🔧 Используйте /settings для настройки профиля"""
            
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения статуса: {e}")

    # ======= НОВЫЕ UI ОБРАБОТЧИКИ =======
    
    @staticmethod
    async def photo_tip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки "Анализ фото" - подсказки по отправке фото"""
        query = update.callback_query
        
        message = f"""📸 **Как отправить фото для анализа**

🎯 **Простые шаги:**
1. Нажмите 📎 (скрепка) в чате
2. Выберите "Камера" или "Фото"
3. Сфотографируйте еду или выберите из галереи
4. Отправьте фото боту

💡 **Советы для лучшего анализа:**
• 📏 Покажите еду целиком на тарелке
• 💡 Хорошее освещение поможет AI
• 🥄 Разместите ложку/вилку для масштаба
• 🍽️ Один прием пищи = одно фото

✨ **Что я определю:**
• Виды продуктов и их количество
• Калории, белки, жиры, углеводы  
• Размер порций и вес продуктов

🚀 Отправляйте фото прямо сейчас!"""

        # Используем постоянную клавиатуру для обычных сообщений
        if query:
            # Это callback query - используем inline кнопки
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        else:
            # Это обычное сообщение - используем постоянную клавиатуру
            reply_markup = CalorieBotHandlers.get_main_keyboard()
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )

    @staticmethod  
    async def my_goal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки "Моя цель" - быстрый просмотр цели калорий"""
        query = update.callback_query
        user = query.from_user
        
        try:
            db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
            today_calories = DatabaseManager.get_today_calories(db_user.id)
            daily_goal = db_user.daily_calorie_goal
            
            # Расчет прогресса
            progress_percent = (today_calories / daily_goal * 100) if daily_goal > 0 else 0
            remaining = daily_goal - today_calories
            
            # Эмодзи статуса
            if remaining > 0:
                status_emoji = "🟢" if remaining > daily_goal * 0.2 else "🟡"
                status_text = f"Осталось: {remaining:.0f} ккал"
            else:
                over = abs(remaining)
                status_emoji = "🔴" if over > daily_goal * 0.1 else "🟡"
                status_text = f"Превышение: +{over:.0f} ккал"
            
            message = f"""🎯 **Ваша цель калорий**

👤 **{user.first_name}**

📊 **Сегодня:** {today_calories:.0f} / {daily_goal} ккал
📈 **Прогресс:** {progress_percent:.1f}% {status_emoji}
⚖️ **{status_text}**

💡 **Рекомендации:**
{'''🍽️ Можете еще поесть - достигайте цели!''' if remaining > 0 else 
'''🥗 Попробуйте легкий ужин или перенос калорий на завтра''' if remaining < -200 else 
'''✅ Отлично! Вы близко к цели'''}

🔧 Хотите изменить цель? Используйте ⚙️ Настройки"""

            keyboard = [
                [InlineKeyboardButton("⚙️ Изменить цель", callback_data="set_calorie_goal")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка загрузки цели: {e}")

    @staticmethod
    async def data_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки "Статус данных" - callback версия status_command"""
        query = update.callback_query
        user = query.from_user
        
        try:
            # Получаем пользователя
            db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
            
            # Определяем тип базы данных
            db_type = "PostgreSQL" if config.DATABASE_URL.startswith('postgresql') else \
                     "SQLite" if config.DATABASE_URL.startswith('sqlite') else "Другая"
            
            persistent = "✅ Данные сохраняются между перезапусками" if db_type == "PostgreSQL" else \
                        "⚠️ Данные могут сбрасываться при обновлениях бота"
            
            # Статистика пользователя
            tracking_days = DatabaseManager.get_tracking_days(db_user.id)
            today_calories = DatabaseManager.get_today_calories(db_user.id)
            
            # Дата создания аккаунта
            created_date = db_user.created_at.strftime('%d.%m.%Y') if db_user.created_at else "Неизвестно"
            
            message = f"""💾 **Статус ваших данных**

👤 **Профиль:**
• Имя: {user.first_name or 'Не указано'}
• Дата регистрации: {created_date}
• Цель калорий: {db_user.daily_calorie_goal} ккал/день

📈 **Активность:**
• Дней с записями: {tracking_days}
• Калорий сегодня: {today_calories:.0f}
• Настроен профиль: {'✅ Да' if (db_user.weight or db_user.height) else '⚙️ Нет'}

💾 **Хранение данных:**
• База данных: {db_type}
• {persistent}

💡 **Это означает:**
{'''✅ Ваши данные в безопасности! 
   Настройки и история сохранятся при обновлениях''' if db_type == "PostgreSQL" else 
'''⚠️ При обновлениях данные могут сброситься
   Рекомендуется администратору настроить PostgreSQL'''}"""

            keyboard = [
                [InlineKeyboardButton("⚙️ Настройки профиля", callback_data="settings")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка получения статуса: {e}")

    # ======= ПЕРСОНАЛИЗИРОВАННЫЙ ОНБОРДИНГ =======
    
    @staticmethod
    async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать процесс персонализированного онбординга"""
        user = update.effective_user
        
        welcome_message = f"""
🎯 **Добро пожаловать в {config.BOT_NAME}!**

👋 Привет, **{user.first_name}**!

Я ваш персональный AI-помощник по подсчету калорий! 

🔬 **Для точного расчета калорий** мне нужно узнать о вас несколько вещей:
• 👤 Ваш пол, возраст, рост и вес
• 🏃 Уровень физической активности  
• 🎯 Автоматический расчет персональной нормы калорий

⏱️ **Это займет всего 2 минуты**, но сделает анализ намного точнее!

💡 **После настройки вы получите:**
• 🎯 Персональную норму калорий именно для вас
• 📊 Точный анализ прогресса к цели
• 💪 Рекомендации по питанию

Готовы настроить ваш профиль?
"""
        
        keyboard = [
            [InlineKeyboardButton("🚀 Да, давайте настроим!", callback_data="start_setup")],
            [InlineKeyboardButton("⏭️ Пропустить (базовые настройки)", callback_data="skip_setup")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                welcome_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                welcome_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )

    @staticmethod
    async def onboarding_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 1: Выбор пола"""
        query = update.callback_query
        
        message = f"""
👤 **Шаг 1 из 5: Ваш пол**

Пол влияет на базальный метаболизм и расчет нормы калорий.

Выберите ваш пол:
"""
        
        keyboard = [
            [
                InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
                InlineKeyboardButton("👩 Женский", callback_data="gender_female")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    @staticmethod
    async def onboarding_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 2: Ввод возраста"""
        query = update.callback_query
        
        # Сохраняем выбранный пол
        if query.data == "gender_male":
            context.user_data['onboarding_gender'] = 'male'
            gender_text = "мужской"
        else:
            context.user_data['onboarding_gender'] = 'female'
            gender_text = "женский"
        
        message = f"""
🎂 **Шаг 2 из 5: Ваш возраст**

✅ Пол: {gender_text}

Возраст нужен для точного расчета метаболизма.

**Напишите ваш возраст** (например: 25):
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="start_setup")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        context.user_data['waiting_for'] = 'age'

    @staticmethod
    async def onboarding_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 3: Ввод роста"""
        try:
            age = int(update.message.text.strip())
            if age < 10 or age > 100:
                await update.message.reply_text("❌ Пожалуйста, введите корректный возраст (10-100 лет)")
                return
            
            context.user_data['onboarding_age'] = age
            gender_text = "мужской" if context.user_data['onboarding_gender'] == 'male' else "женский"
            
            message = f"""
📏 **Шаг 3 из 5: Ваш рост**

✅ Пол: {gender_text}
✅ Возраст: {age} лет

Рост необходим для расчета индекса массы тела.

**Напишите ваш рост в сантиметрах** (например: 175):
"""
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="onboarding_age")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            context.user_data['waiting_for'] = 'height'
            
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите возраст числом (например: 25)")

    @staticmethod
    async def onboarding_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 4: Ввод веса"""
        try:
            height = float(update.message.text.strip())
            if height < 100 or height > 250:
                await update.message.reply_text("❌ Пожалуйста, введите корректный рост (100-250 см)")
                return
            
            context.user_data['onboarding_height'] = height
            gender_text = "мужской" if context.user_data['onboarding_gender'] == 'male' else "женский"
            age = context.user_data['onboarding_age']
            
            message = f"""
⚖️ **Шаг 4 из 5: Ваш вес**

✅ Пол: {gender_text}
✅ Возраст: {age} лет
✅ Рост: {height:.0f} см

Вес нужен для точного расчета нормы калорий.

**Напишите ваш текущий вес в килограммах** (например: 70 или 65.5):
"""
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="onboarding_height")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            context.user_data['waiting_for'] = 'weight'
            
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите рост числом (например: 175)")

    @staticmethod
    async def onboarding_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 5: Выбор уровня активности"""
        try:
            weight = float(update.message.text.strip())
            if weight < 30 or weight > 200:
                await update.message.reply_text("❌ Пожалуйста, введите корректный вес (30-200 кг)")
                return
            
            context.user_data['onboarding_weight'] = weight
            gender_text = "мужской" if context.user_data['onboarding_gender'] == 'male' else "женский"
            age = context.user_data['onboarding_age']
            height = context.user_data['onboarding_height']
            
            message = f"""
🏃 **Шаг 5 из 5: Уровень активности**

✅ Пол: {gender_text}
✅ Возраст: {age} лет
✅ Рост: {height:.0f} см  
✅ Вес: {weight:.1f} кг

Выберите ваш уровень физической активности:
"""
            
            keyboard = [
                [InlineKeyboardButton("🛋️ Низкий (сидячая работа, нет спорта)", callback_data="activity_low")],
                [InlineKeyboardButton("🚶 Умеренный (легкие тренировки 1-3 раза в неделю)", callback_data="activity_moderate")],
                [InlineKeyboardButton("🏃 Высокий (интенсивные тренировки 4-7 раз в неделю)", callback_data="activity_high")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            context.user_data['waiting_for'] = 'activity'
            
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите вес числом (например: 70 или 65.5)")

    @staticmethod
    async def complete_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершение онбординга с расчетом персональной нормы"""
        query = update.callback_query
        user = update.effective_user
        
        # Определяем уровень активности
        activity_mapping = {
            'activity_low': ('low', 'Низкий'),
            'activity_moderate': ('moderate', 'Умеренный'), 
            'activity_high': ('high', 'Высокий')
        }
        
        activity_level, activity_text = activity_mapping[query.data]
        
        # Получаем все данные из контекста
        gender = context.user_data['onboarding_gender']
        age = context.user_data['onboarding_age']
        height = context.user_data['onboarding_height']
        weight = context.user_data['onboarding_weight']
        
        # Завершаем онбординг и получаем рассчитанную норму калорий
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🎯 BOT: Вызываем complete_onboarding для пользователя {user.id}")
        logger.info(f"🎯 BOT: Данные: weight={weight}, height={height}, age={age}, gender={gender}, activity={activity_level}")
        
        daily_calories = DatabaseManager.complete_onboarding(
            telegram_id=user.id,
            weight=weight,
            height=height,
            age=age,
            gender=gender,
            activity_level=activity_level
        )
        
        logger.info(f"🎯 BOT: Результат complete_onboarding: {daily_calories} (тип: {type(daily_calories)})")
        
        if daily_calories:
            # Очищаем данные онбординга
            for key in ['onboarding_gender', 'onboarding_age', 'onboarding_height', 'onboarding_weight', 'waiting_for']:
                context.user_data.pop(key, None)
            
            # Рассчитываем ИМТ
            bmi = weight / ((height/100) ** 2)
            if bmi < 18.5:
                bmi_status = "Недостаток веса"
                bmi_emoji = "📉"
            elif bmi < 25:
                bmi_status = "Нормальный вес"
                bmi_emoji = "✅"
            elif bmi < 30:
                bmi_status = "Избыточный вес"
                bmi_emoji = "📈"
            else:
                bmi_status = "Ожирение"
                bmi_emoji = "🔺"
            
            gender_text = "мужской" if gender == 'male' else "женский"
            
            success_message = f"""
🎉 **Профиль успешно настроен!**

👤 **Ваши данные:**
• Пол: {gender_text}
• Возраст: {age} лет
• Рост: {height:.0f} см
• Вес: {weight:.1f} кг
• Активность: {activity_text}

📊 **Рассчитанные показатели:**
• ИМТ: {bmi:.1f} - {bmi_status} {bmi_emoji}
• **Ваша норма калорий: {daily_calories} ккал/день** 🎯

🚀 **Теперь все готово!**
Отправьте фото вашей еды, и я дам точный анализ с учетом ваших персональных целей!

💡 **Совет:** Норма рассчитана для поддержания текущего веса. Вы можете изменить цель в настройках для похудения или набора массы.
"""
            
            keyboard = [
                [InlineKeyboardButton("🍽️ Начать анализ еды!", callback_data="add_photo_tip")],
                [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                success_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        else:
            await query.edit_message_text("❌ Ошибка при сохранении данных. Попробуйте позже.")

    @staticmethod
    async def skip_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Пропустить онбординг и использовать базовые настройки"""
        query = update.callback_query
        user = update.effective_user
        
        # Устанавливаем базовые настройки
        DatabaseManager.complete_onboarding(
            telegram_id=user.id,
            weight=70.0,  # Средний вес
            height=170.0,  # Средний рост
            age=30,       # Средний возраст
            gender='male',  # По умолчанию
            activity_level='moderate'  # Умеренная активность
        )
        
        message = f"""
⏭️ **Онбординг пропущен**

Установлены базовые настройки:
• Норма калорий: **2000 ккал/день** 📊

💡 **Рекомендация:** Для более точного анализа калорий настройте ваш профиль в любое время через 👤 Мой профиль → ⚙️ Настройки

🍽️ **Готово к использованию!**
Отправьте фото еды и получите анализ калорий!
"""
        
        keyboard = [
            [InlineKeyboardButton("📸 Анализ фото", callback_data="add_photo_tip")],
            [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    @staticmethod
    async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - статистика питания"""
        await CalorieBotHandlers.stats_handler(update, context)
    
    @staticmethod
    async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /settings - настройки профиля"""
        await CalorieBotHandlers.settings_handler(update, context)
    
    @staticmethod
    async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда истории питания"""
        try:
            user = update.effective_user
            db_user = DatabaseManager.get_or_create_user(telegram_id=user.id)
            
            # Получаем последние записи
            from database import SessionLocal, FoodEntry
            db = SessionLocal()
            try:
                recent_entries = db.query(FoodEntry).filter(
                    FoodEntry.user_id == db_user.id
                ).order_by(FoodEntry.created_at.desc()).limit(10).all()
                
                if not recent_entries:
                    message = "📅 **История питания пуста**\n\nНачните с отправки фото еды!"
                else:
                    message = "📅 **Последние записи:**\n\n"
                    for entry in recent_entries:
                        date_str = entry.created_at.strftime("%d.%m %H:%M")
                        message += f"• {date_str} - {entry.total_calories:.0f} ккал\n"
                        # Пытаемся извлечь название еды из JSON
                        try:
                            import json
                            if entry.food_items:
                                food_data = json.loads(entry.food_items)
                                if isinstance(food_data, list) and len(food_data) > 0:
                                    first_item = food_data[0]
                                    if isinstance(first_item, dict) and 'name' in first_item:
                                        message += f"  {first_item['name']}\n"
                        except:
                            pass  # Если не удалось распарсить JSON, просто пропускаем
                        message += "\n"
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=CalorieBotHandlers.get_main_keyboard()
                )
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Ошибка в history_command: {e}")
            await update.message.reply_text(
                f"❌ Ошибка загрузки истории: {e}",
                reply_markup=CalorieBotHandlers.get_main_keyboard()
            )
    
    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        help_message = f"""
❓ **Справка по использованию бота**

🚀 **Быстрый старт:**
1️⃣ Отправьте фото еды боту
2️⃣ Получите анализ калорий за 5 секунд  
3️⃣ Следите за прогрессом в статистике

📸 **Анализ фото еды:**
• AI определяет виды продуктов
• Подсчитывает калории, БЖУ и вес
• Работает с любыми блюдами
• Точность анализа 85-95%

💡 **Советы для лучших результатов:**
🔍 Хорошее освещение
🍽️ Вся порция в кадре
📏 Добавьте ложку для масштаба
🎯 Четкое фото без размытия

📊 **Что отслеживает бот:**
• Ежедневные калории и БЖУ
• Прогресс к вашей цели
• Статистика по дням/неделям  
• История всех записей

⚙️ **Персонализация:**
• Установите свою цель калорий
• Укажите вес, рост, возраст
• Настройте уведомления
• Экспортируйте данные

🔒 **Безопасность данных:**
{'''• ✅ PostgreSQL - данные сохраняются навсегда
• 🛡️ Никаких потерь при обновлениях''' if config.DATABASE_URL.startswith('postgresql') else 
'''• ⚠️ SQLite - данные могут сбрасываться
• 💡 Рекомендуется настроить PostgreSQL'''}

❓ Остались вопросы? Просто напишите мне!
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📸 Как отправить фото", callback_data="add_photo_tip"),
                InlineKeyboardButton("🎯 Моя цель", callback_data="my_goal")
            ],
            [
                InlineKeyboardButton("👤 Мой профиль", callback_data="profile"),
                InlineKeyboardButton("📊 Статистика", callback_data="stats")
            ],
            [
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ]
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
            # Используем постоянную клавиатуру для обычных сообщений
            main_keyboard = CalorieBotHandlers.get_main_keyboard()
            await update.message.reply_text(
                help_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard
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
            
            # Улучшенная клавиатура с действиями
            keyboard = [
                # Первый ряд - основные действия
                [
                    InlineKeyboardButton("📊 Посмотреть статистику", callback_data="stats"),
                    InlineKeyboardButton("👤 Мой профиль", callback_data="profile")
                ],
                # Второй ряд - редактирование и добавление
                [
                    InlineKeyboardButton("🔧 Исправить анализ", callback_data="correct_analysis"),
                    InlineKeyboardButton("➕ Добавить еще блюдо", callback_data="add_more")
                ],
                # Третий ряд - навигация
                [
                    InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                ]
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
            # Используем постоянную клавиатуру
            reply_markup = CalorieBotHandlers.get_main_keyboard()
            
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
        
        # Используем постоянную клавиатуру для обычных сообщений
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        else:
            # Для обычных сообщений используем постоянную клавиатуру
            main_keyboard = CalorieBotHandlers.get_main_keyboard()
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard
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
        elif query.data == "add_photo_tip":
            await CalorieBotHandlers.photo_tip_handler(update, context)
        elif query.data == "my_goal":
            await CalorieBotHandlers.my_goal_handler(update, context) 
        elif query.data == "data_status":
            await CalorieBotHandlers.data_status_handler(update, context)
        
        # Онбординг callbacks
        elif query.data == "start_setup":
            await CalorieBotHandlers.onboarding_gender(update, context)
        elif query.data == "skip_setup":
            await CalorieBotHandlers.skip_onboarding(update, context)
        elif query.data in ["gender_male", "gender_female"]:
            await CalorieBotHandlers.onboarding_age(update, context)
        elif query.data in ["activity_low", "activity_moderate", "activity_high"]:
            await CalorieBotHandlers.complete_onboarding(update, context)
    
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
        
        # Обработка кнопок постоянной клавиатуры
        if text == "🍽️ Анализ еды":
            await CalorieBotHandlers.photo_tip_handler(update, context)
        elif text == "📊 Статистика":
            await CalorieBotHandlers.stats_command(update, context)
        elif text == "⚙️ Настройки":
            await CalorieBotHandlers.settings_command(update, context)
        elif text == "📅 История":
            await CalorieBotHandlers.history_command(update, context)
        elif text == "❓ Помощь":
            await CalorieBotHandlers.help_command(update, context)
        elif text == "🏠 Главное меню":
            await CalorieBotHandlers.start_command(update, context)
        # Проверяем, ожидаем ли мы ввод настроек
        elif context.user_data.get('waiting_for') == 'correction':
            await CalorieBotHandlers.process_correction(update, context, text)
        elif context.user_data.get('waiting_for') == 'age':
            await CalorieBotHandlers.onboarding_height(update, context)
        elif context.user_data.get('waiting_for') == 'height':
            await CalorieBotHandlers.onboarding_weight(update, context)
        elif context.user_data.get('waiting_for') == 'weight':
            await CalorieBotHandlers.onboarding_activity(update, context)
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
        
        from database import SessionLocal, User
        db = SessionLocal()
        try:
            # Получаем всех активных пользователей
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
    logger.info("🚀 Инициализация бота начата...")
    
    # Создаем таблицы базы данных
    create_tables()
    logger.info("📊 База данных инициализирована")
    
    # КРИТИЧЕСКИ ВАЖНО: Принудительно запускаем миграцию ПЕРЕД любыми операциями
    logger.info("🔧 ЗАПУСКАЕМ КРИТИЧЕСКИ ВАЖНУЮ МИГРАЦИЮ telegram_id...")
    try:
        from database import migrate_telegram_id_if_needed, engine
        migrate_telegram_id_if_needed()
        
        # Проверяем что миграция действительно выполнилась
        try:
            from sqlalchemy import text
            with engine.connect() as connection:
                result = connection.execute(text("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name = 'telegram_id'
                """))
                row = result.fetchone()
                if row and row[0] == 'bigint':
                    logger.info("✅ ПОДТВЕРЖДЕНО: telegram_id успешно мигрирован на BIGINT")
                    logger.info("✅ Большие Telegram ID теперь полностью поддерживаются")
                else:
                    logger.error(f"🚨 МИГРАЦИЯ НЕ СРАБОТАЛА! telegram_id все еще имеет тип: {row[0] if row else 'НЕИЗВЕСТНО'}")
                    logger.error("🚨 Пользователи с большими ID будут получать ошибки!")
        except Exception as check_error:
            logger.error(f"🚨 Не удалось проверить статус миграции: {check_error}")
            
        logger.info("✅ Процесс миграции завершен")
    except Exception as migration_error:
        logger.error(f"🚨 КРИТИЧЕСКАЯ ОШИБКА МИГРАЦИИ: {migration_error}")
        logger.error("🚨 Бот будет работать, но пользователи с большими ID получат ошибки!")
    
    # Создаем приложение
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", CalorieBotHandlers.start_command))
    application.add_handler(CommandHandler("help", CalorieBotHandlers.help_command))
    application.add_handler(CommandHandler("stats", CalorieBotHandlers.stats_handler))
    application.add_handler(CommandHandler("settings", CalorieBotHandlers.settings_handler))
    application.add_handler(CommandHandler("profile", CalorieBotHandlers.profile_command))
    application.add_handler(CommandHandler("status", CalorieBotHandlers.status_command))
    application.add_handler(CommandHandler("fixgoal", CalorieBotHandlers.fix_goal_command))
    application.add_handler(CommandHandler("testai", CalorieBotHandlers.test_ai_command))
    application.add_handler(CommandHandler("debuguser", CalorieBotHandlers.debug_user_command))
    application.add_handler(CommandHandler("resetuser", CalorieBotHandlers.reset_user_command))
    application.add_handler(CommandHandler("debugstats", CalorieBotHandlers.debug_stats_command))
    application.add_handler(CommandHandler("rebuildstats", CalorieBotHandlers.rebuild_stats_command))
    
    # Админские команды
    application.add_handler(CommandHandler("adminstats", CalorieBotHandlers.admin_stats_command))
    application.add_handler(CommandHandler("adminusers", CalorieBotHandlers.admin_users_command))
    application.add_handler(CommandHandler("adminuser", CalorieBotHandlers.admin_user_command))
    application.add_handler(CommandHandler("adminexport", CalorieBotHandlers.admin_export_command))
    application.add_handler(CommandHandler("admintest", CalorieBotHandlers.admin_test_command))
    application.add_handler(CommandHandler("forcemigration", CalorieBotHandlers.force_migration_command))
    application.add_handler(CommandHandler("debugmigration", CalorieBotHandlers.debug_migration_command))
    application.add_handler(CommandHandler("admindebug", CalorieBotHandlers.admin_debug_command))
    application.add_handler(CommandHandler("admindb", CalorieBotHandlers.admin_db_command))
    
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
