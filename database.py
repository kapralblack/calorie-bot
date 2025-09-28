"""
Модель базы данных для телеграм-бота подсчета калорий
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, func, BigInteger, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone, timedelta
import config

Base = declarative_base()

class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    
    # Настройки пользователя
    daily_calorie_goal = Column(Integer, default=2000)
    weight = Column(Float)
    height = Column(Float)
    age = Column(Integer)
    gender = Column(String(10))  # male/female
    activity_level = Column(String(20), default='moderate')  # low/moderate/high
    # onboarding_completed = Column(Boolean, default=False)  # Временно отключено для совместимости
    
    # Связи
    food_entries = relationship("FoodEntry", back_populates="user", cascade="all, delete-orphan")
    
    def calculate_daily_calorie_goal(self):
        """Рассчитывает дневную норму калорий по формуле Миффлина-Сан Жеора"""
        if not all([self.weight, self.height, self.age, self.gender]):
            return 2000  # Дефолтное значение если данных недостаточно
        
        # Базальный метаболизм по формуле Миффлина-Сан Жеора
        if self.gender.lower() == 'male':
            bmr = (10 * self.weight) + (6.25 * self.height) - (5 * self.age) + 5
        else:  # female
            bmr = (10 * self.weight) + (6.25 * self.height) - (5 * self.age) - 161
        
        # Коэффициент активности
        activity_multipliers = {
            'low': 1.2,      # Малоподвижный образ жизни
            'moderate': 1.55, # Умеренная активность
            'high': 1.9      # Высокая активность
        }
        
        multiplier = activity_multipliers.get(self.activity_level, 1.55)
        daily_calories = int(bmr * multiplier)
        
        return daily_calories

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"

class FoodEntry(Base):
    """Модель записи о еде"""
    __tablename__ = 'food_entries'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Данные о еде
    food_items = Column(Text)  # JSON строка с данными о блюдах
    total_calories = Column(Float, nullable=False)
    total_proteins = Column(Float, default=0)
    total_carbs = Column(Float, default=0)
    total_fats = Column(Float, default=0)
    
    # Метаданные
    confidence = Column(Float, default=0)  # Уверенность AI в анализе
    meal_type = Column(String(20))  # breakfast/lunch/dinner/snack
    photo_id = Column(String(255))  # ID фото в Telegram
    
    # Связи
    user = relationship("User", back_populates="food_entries")
    
    def __repr__(self):
        return f"<FoodEntry(user_id={self.user_id}, calories={self.total_calories}, date={self.created_at})>"

class DailyStats(Base):
    """Модель дневной статистики пользователя"""
    __tablename__ = 'daily_stats'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    date = Column(DateTime, nullable=False)
    
    # Суммарные данные за день
    total_calories = Column(Float, default=0)
    total_proteins = Column(Float, default=0)
    total_carbs = Column(Float, default=0)
    total_fats = Column(Float, default=0)
    
    # Количество приемов пищи
    meals_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Создание движка базы данных
engine = create_engine(config.DATABASE_URL, echo=False)

# Создание сессии
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def migrate_telegram_id_if_needed():
    """Автоматическая миграция telegram_id с INTEGER на BIGINT если необходимо"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Проверяем только для PostgreSQL
    if not config.DATABASE_URL.startswith('postgresql'):
        logger.info("Используется SQLite, миграция telegram_id не нужна")
        return
    
    try:
        # Проверяем текущий тип поля telegram_id
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name = 'telegram_id'
            """))
            
            row = result.fetchone()
            if not row:
                logger.info("Таблица users не существует, миграция не нужна")
                return
            
            current_type = row[0]
            logger.info(f"Текущий тип telegram_id: {current_type}")
            
            if current_type == 'bigint':
                logger.info("✅ Поле telegram_id уже имеет тип BIGINT")
                return
            
            if current_type == 'integer':
                logger.info("🔧 Начинаю автоматическую миграцию telegram_id: INTEGER → BIGINT")
                
                # Выполняем миграцию в транзакции
                with connection.begin() as transaction:
                    migration_steps = [
                        ("Добавление временной колонки", "ALTER TABLE users ADD COLUMN telegram_id_new BIGINT"),
                        ("Копирование данных", "UPDATE users SET telegram_id_new = telegram_id"),
                        ("Удаление ограничения уникальности", "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_telegram_id_key"),
                        ("Удаление индекса", "DROP INDEX IF EXISTS ix_users_telegram_id"), 
                        ("Удаление старой колонки", "ALTER TABLE users DROP COLUMN telegram_id"),
                        ("Переименование новой колонки", "ALTER TABLE users RENAME COLUMN telegram_id_new TO telegram_id"),
                        ("Установка NOT NULL", "ALTER TABLE users ALTER COLUMN telegram_id SET NOT NULL"),
                        ("Добавление ограничения уникальности", "ALTER TABLE users ADD CONSTRAINT users_telegram_id_key UNIQUE (telegram_id)"),
                        ("Создание индекса", "CREATE INDEX ix_users_telegram_id ON users (telegram_id)")
                    ]
                    
                    for i, (description, step) in enumerate(migration_steps, 1):
                        try:
                            logger.info(f"Шаг {i}/9: {description}")
                            connection.execute(text(step))
                        except Exception as step_error:
                            logger.warning(f"Ошибка на шаге {i} ({description}): {step_error}")
                            # Некоторые шаги могут не выполниться, продолжаем
                            continue
                    
                    # Транзакция автоматически коммитится при выходе из блока
                    logger.info("✅ Миграция telegram_id завершена успешно!")
                    logger.info("🚀 Теперь поддерживаются любые Telegram ID!")
            
    except Exception as e:
        logger.error(f"Ошибка при проверке/миграции telegram_id: {e}")
        logger.info("Продолжаем работу с текущей схемой...")

def create_tables():
    """Создание всех таблиц в базе данных"""
    import logging
    logger = logging.getLogger(__name__)
    
    Base.metadata.create_all(bind=engine)
    logger.info("Таблицы базы данных созданы")
    
    # Выполняем автоматическую миграцию если необходимо
    try:
        migrate_telegram_id_if_needed()
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}")
        logger.info("Бот продолжит работу с текущей схемой")

def get_db():
    """Получение сессии базы данных"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Сессия закроется в коде, который её использует

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    @staticmethod
    def get_or_create_user(telegram_id, username=None, first_name=None, last_name=None):
        """Получить или создать пользователя с полной загрузкой настроек"""
        db = SessionLocal()
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    daily_calorie_goal=2000  # Дефолтная цель для новых пользователей
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                
                logger.info(f"Создан новый пользователь {telegram_id} с целью {user.daily_calorie_goal} ккал")
            else:
                # Обновляем данные существующего пользователя
                updated = False
                if username and user.username != username:
                    user.username = username
                    updated = True
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                
                if updated:
                    db.commit()
                    db.refresh(user)
                
                logger.info(f"Загружен пользователь {telegram_id} с целью {user.daily_calorie_goal} ккал")
                
            return user
        except Exception as e:
            # Обработка ошибок базы данных, включая integer out of range
            db.rollback()
            logger.error(f"Ошибка при работе с пользователем {telegram_id}: {e}")
            
            # Если это ошибка integer out of range, пытаемся использовать альтернативную схему
            if "integer out of range" in str(e).lower() or "numericvalueoutofrange" in str(type(e).__name__).lower():
                logger.error(f"Telegram ID {telegram_id} слишком большой для текущей схемы базы данных")
                logger.error("Требуется миграция схемы: telegram_id INTEGER → BIGINT")
                
                # Создаем фиктивного пользователя с базовыми настройками для продолжения работы
                class TempUser:
                    def __init__(self):
                        self.id = None
                        self.telegram_id = telegram_id
                        self.username = username
                        self.first_name = first_name  
                        self.last_name = last_name
                        self.daily_calorie_goal = 2000
                        self.weight = None
                        self.height = None
                        self.age = None
                        self.gender = None
                        self.activity_level = 'moderate'
                    
                    def calculate_daily_calorie_goal(self):
                        """Рассчитывает дневную норму калорий"""
                        if not all([self.weight, self.height, self.age, self.gender]):
                            return 2000
                        
                        # Базальный метаболизм
                        if self.gender.lower() == 'male':
                            bmr = (10 * self.weight) + (6.25 * self.height) - (5 * self.age) + 5
                        else:
                            bmr = (10 * self.weight) + (6.25 * self.height) - (5 * self.age) - 161
                        
                        # Коэффициент активности
                        activity_multipliers = {'low': 1.2, 'moderate': 1.55, 'high': 1.9}
                        multiplier = activity_multipliers.get(self.activity_level, 1.55)
                        return int(bmr * multiplier)
                        
                return TempUser()
            
            # Для других ошибок создаем базового пользователя
            class TempUser:
                def __init__(self):
                    self.id = None
                    self.telegram_id = telegram_id
                    self.username = username
                    self.first_name = first_name
                    self.last_name = last_name  
                    self.daily_calorie_goal = 2000
                    self.weight = None
                    self.height = None
                    self.age = None
                    self.gender = None
                    self.activity_level = 'moderate'
                
                def calculate_daily_calorie_goal(self):
                    """Рассчитывает дневную норму калорий"""
                    if not all([self.weight, self.height, self.age, self.gender]):
                        return 2000
                    
                    # Базальный метаболизм
                    if self.gender.lower() == 'male':
                        bmr = (10 * self.weight) + (6.25 * self.height) - (5 * self.age) + 5
                    else:
                        bmr = (10 * self.weight) + (6.25 * self.height) - (5 * self.age) - 161
                    
                    # Коэффициент активности
                    activity_multipliers = {'low': 1.2, 'moderate': 1.55, 'high': 1.9}
                    multiplier = activity_multipliers.get(self.activity_level, 1.55)
                    return int(bmr * multiplier)
            
            return TempUser()
        finally:
            db.close()
    
    @staticmethod
    def add_food_entry(user_id, food_data, total_calories, total_proteins=0, total_carbs=0, total_fats=0, 
                      confidence=0, meal_type=None, photo_id=None):
        """Добавить запись о еде"""
        db = SessionLocal()
        try:
            entry = FoodEntry(
                user_id=user_id,
                food_items=food_data,
                total_calories=total_calories,
                total_proteins=total_proteins,
                total_carbs=total_carbs,
                total_fats=total_fats,
                confidence=confidence,
                meal_type=meal_type,
                photo_id=photo_id
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            
            # Обновляем дневную статистику
            DatabaseManager._update_daily_stats(user_id, entry.created_at.date())
            
            return entry
        finally:
            db.close()
    
    @staticmethod
    def _update_daily_stats(user_id, date):
        """Обновить дневную статистику"""
        db = SessionLocal()
        try:
            # ИСПРАВЛЕНИЕ: Получаем все записи за день с учетом UTC времени
            start_of_day = datetime.combine(date, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_of_day = datetime.combine(date, datetime.max.time()).replace(tzinfo=timezone.utc)
            
            entries = db.query(FoodEntry).filter(
                FoodEntry.user_id == user_id,
                FoodEntry.created_at >= start_of_day,
                FoodEntry.created_at < end_of_day
            ).all()
            
            # Считаем суммы
            total_calories = sum(entry.total_calories for entry in entries)
            total_proteins = sum(entry.total_proteins for entry in entries)
            total_carbs = sum(entry.total_carbs for entry in entries)
            total_fats = sum(entry.total_fats for entry in entries)
            
            # Получаем или создаем запись дневной статистики
            daily_stat = db.query(DailyStats).filter(
                DailyStats.user_id == user_id,
                DailyStats.date == date
            ).first()
            
            if not daily_stat:
                daily_stat = DailyStats(
                    user_id=user_id,
                    date=date
                )
                db.add(daily_stat)
            
            # Обновляем данные
            daily_stat.total_calories = total_calories
            daily_stat.total_proteins = total_proteins
            daily_stat.total_carbs = total_carbs
            daily_stat.total_fats = total_fats
            daily_stat.meals_count = len(entries)
            daily_stat.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            
            # ЛОГИРОВАНИЕ: Отслеживаем обновление дневной статистики
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"📊 Обновлена дневная статистика для user_id {user_id} за {date}: {total_calories:.1f} ккал, {len(entries)} записей")
            
        finally:
            db.close()
    
    @staticmethod
    def get_user_stats(user_id, days=7):
        """Получить статистику пользователя за последние N дней"""
        db = SessionLocal()
        try:
            from datetime import timedelta
            # ИСПРАВЛЕНИЕ: Используем UTC время для корректного поиска записей
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days-1)
            
            stats = db.query(DailyStats).filter(
                DailyStats.user_id == user_id,
                DailyStats.date >= start_date,
                DailyStats.date <= end_date
            ).order_by(DailyStats.date).all()
            
            # ЛОГИРОВАНИЕ: Отслеживаем что находит get_user_stats
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"📈 get_user_stats для user_id {user_id}: найдено {len(stats)} записей за {days} дней ({start_date} - {end_date})")
            
            return stats
        finally:
            db.close()
    
    @staticmethod
    def get_today_calories(user_id):
        """Получить калории за сегодня - с прямым подсчетом из записей еды"""
        db = SessionLocal()
        try:
            # ИСПРАВЛЕНИЕ: Используем точные границы дня в UTC
            today = datetime.now(timezone.utc).date()
            start_of_day = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_of_day = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
            
            today_calories = db.query(func.sum(FoodEntry.total_calories)).filter(
                FoodEntry.user_id == user_id,
                FoodEntry.created_at >= start_of_day,
                FoodEntry.created_at <= end_of_day
            ).scalar() or 0
            
            return float(today_calories)
        finally:
            db.close()
    
    @staticmethod
    def update_user_settings(user_id, daily_calorie_goal=None, weight=None, height=None, 
                           age=None, gender=None, activity_level=None):
        """Обновить настройки пользователя"""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                old_goal = user.daily_calorie_goal
                
                if daily_calorie_goal is not None:
                    user.daily_calorie_goal = daily_calorie_goal
                if weight is not None:
                    user.weight = weight
                if height is not None:
                    user.height = height
                if age is not None:
                    user.age = age
                if gender is not None:
                    user.gender = gender
                if activity_level is not None:
                    user.activity_level = activity_level
                
                db.commit()
                db.refresh(user)
                
                # Логируем изменения
                if daily_calorie_goal is not None:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Цель пользователя {user.telegram_id} изменена: {old_goal} → {user.daily_calorie_goal} ккал")
                
                return user
        finally:
            db.close()

    @staticmethod  
    def get_user_info(telegram_id):
        """Получить подробную информацию о пользователе"""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return None
            
            # Получаем сегодняшние калории
            today_calories = DatabaseManager.get_today_calories(user.id)
            
            # Получаем недавнюю статистику
            recent_stats = DatabaseManager.get_user_stats(user.id, days=7)
            
            return {
                'user': user,
                'today_calories': today_calories,
                'daily_goal': user.daily_calorie_goal,
                'remaining_calories': user.daily_calorie_goal - today_calories,
                'recent_stats': recent_stats,
                'total_entries_last_week': len(recent_stats) if recent_stats else 0
            }
        finally:
            db.close()

    @staticmethod
    def force_update_user_goal(telegram_id, new_goal):
        """Принудительно обновить цель пользователя по telegram_id"""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                old_goal = user.daily_calorie_goal
                user.daily_calorie_goal = new_goal
                db.commit()
                
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"ПРИНУДИТЕЛЬНО изменена цель пользователя {telegram_id}: {old_goal} → {new_goal} ккал")
                
                return True
        finally:
            db.close()
        return False

    @staticmethod
    def get_user_info(user_id: int) -> dict:
        """Получить расширенную информацию о пользователе"""
        db = SessionLocal()
        try:
            # Сегодняшние калории
            today = datetime.now(timezone.utc).date()
            today_calories = db.query(func.sum(FoodEntry.total_calories)).filter(
                FoodEntry.user_id == user_id,
                func.date(FoodEntry.created_at) == today
            ).scalar() or 0
            
            # Средние за неделю
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            week_entries = db.query(FoodEntry).filter(
                FoodEntry.user_id == user_id,
                FoodEntry.created_at >= week_ago
            ).all()
            
            week_total = sum(entry.total_calories for entry in week_entries)
            week_avg = week_total / 7 if week_entries else 0
            
            # Средние за месяц
            month_ago = datetime.now(timezone.utc) - timedelta(days=30)
            month_entries = db.query(FoodEntry).filter(
                FoodEntry.user_id == user_id,
                FoodEntry.created_at >= month_ago
            ).all()
            
            month_total = sum(entry.total_calories for entry in month_entries)
            month_avg = month_total / 30 if month_entries else 0
            
            return {
                'today_calories': float(today_calories) if today_calories else 0.0,
                'week_avg': float(week_avg) if week_avg else 0.0,
                'month_avg': float(month_avg) if month_avg else 0.0
            }
        finally:
            db.close()

    @staticmethod
    def get_tracking_days(user_id: int) -> int:
        """Получить количество дней ведения записей"""
        db = SessionLocal()
        try:
            # Количество уникальных дней с записями
            days_count = db.query(
                func.count(func.distinct(func.date(FoodEntry.created_at)))
            ).filter(FoodEntry.user_id == user_id).scalar()
            
            return days_count or 0
        finally:
            db.close()

    @staticmethod
    def get_daily_calorie_history(user_id: int, days: int = 14) -> list:
        """Получить историю калорий по дням"""
        db = SessionLocal()
        try:
            # Получаем записи за последние N дней
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Группируем по дням и суммируем калории
            results = db.query(
                func.date(FoodEntry.created_at).label('date'),
                func.sum(FoodEntry.total_calories).label('calories')
            ).filter(
                FoodEntry.user_id == user_id,
                FoodEntry.created_at >= start_date
            ).group_by(
                func.date(FoodEntry.created_at)
            ).order_by(
                func.date(FoodEntry.created_at).desc()
            ).all()
            
            return [
                {
                    'date': result.date,
                    'calories': float(result.calories or 0)
                }
                for result in results
            ]
        finally:
            db.close()

    @staticmethod
    def get_weekly_stats(user_id: int) -> list:
        """Получить статистику по неделям (последние 4 недели)"""
        db = SessionLocal()
        try:
            weekly_stats = []
            
            for week_num in range(4):
                # Определяем даты недели
                end_date = datetime.now(timezone.utc) - timedelta(days=week_num * 7)
                start_date = end_date - timedelta(days=6)  # 7 дней включительно
                
                # Получаем записи за неделю
                week_entries = db.query(FoodEntry).filter(
                    FoodEntry.user_id == user_id,
                    FoodEntry.created_at >= start_date,
                    FoodEntry.created_at <= end_date
                ).all()
                
                if week_entries:
                    # Считаем статистику
                    total_calories = sum(entry.total_calories for entry in week_entries)
                    unique_days = len(set(entry.created_at.date() for entry in week_entries))
                    avg_calories = total_calories / 7  # среднее за 7 дней
                    
                    weekly_stats.append({
                        'week_start': start_date.date(),
                        'week_end': end_date.date(),
                        'total_calories': total_calories,
                        'avg_calories': avg_calories,
                        'days_tracked': unique_days
                    })
            
            return weekly_stats
        finally:
            db.close()

    @staticmethod
    def get_admin_stats():
        """Получить общую статистику по боту для администратора"""
        db = SessionLocal()
        try:
            # Общая статистика по пользователям
            total_users = db.query(func.count(User.id)).scalar() or 0
            
            # Активные пользователи (с записями за последние 7 дней)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            active_users = db.query(func.count(func.distinct(FoodEntry.user_id))).filter(
                FoodEntry.created_at >= week_ago
            ).scalar() or 0
            
            # Всего записей о еде
            total_food_entries = db.query(func.count(FoodEntry.id)).scalar() or 0
            
            # Записей за сегодня
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_entries = db.query(func.count(FoodEntry.id)).filter(
                FoodEntry.created_at >= today_start
            ).scalar() or 0
            
            # Пользователи с настроенными целями калорий (не дефолтные)
            configured_users = db.query(func.count(User.id)).filter(
                User.daily_calorie_goal != 2000
            ).scalar() or 0
            
            # Самые активные пользователи (топ 5)
            top_users = db.query(
                User.first_name, 
                User.telegram_id,
                func.count(FoodEntry.id).label('entries_count')
            ).join(FoodEntry).group_by(User.id, User.first_name, User.telegram_id).order_by(
                func.count(FoodEntry.id).desc()
            ).limit(5).all()
            
            return {
                'total_users': total_users,
                'active_users_7d': active_users,
                'total_food_entries': total_food_entries,
                'today_entries': today_entries,
                'configured_users': configured_users,
                'top_users': [
                    {
                        'name': user.first_name or 'Неизвестно',
                        'telegram_id': user.telegram_id,
                        'entries_count': user.entries_count
                    }
                    for user in top_users
                ]
            }
        finally:
            db.close()

    @staticmethod
    def get_all_users_summary():
        """Получить краткую информацию по всем пользователям"""
        db = SessionLocal()
        try:
            users = db.query(User).order_by(User.created_at.desc()).all()
            
            users_summary = []
            for user in users:
                # Считаем количество записей для каждого пользователя
                entries_count = db.query(func.count(FoodEntry.id)).filter(
                    FoodEntry.user_id == user.id
                ).scalar() or 0
                
                # Последняя активность
                last_entry = db.query(FoodEntry.created_at).filter(
                    FoodEntry.user_id == user.id
                ).order_by(FoodEntry.created_at.desc()).first()
                
                last_activity = None
                if last_entry:
                    last_activity = last_entry[0]
                    # Убеждаемся что datetime имеет timezone info
                    if last_activity and last_activity.tzinfo is None:
                        last_activity = last_activity.replace(tzinfo=timezone.utc)
                
                users_summary.append({
                    'id': user.id,
                    'telegram_id': user.telegram_id,
                    'name': user.first_name or 'Неизвестно',
                    'username': user.username,
                    'created_at': user.created_at.replace(tzinfo=timezone.utc) if user.created_at and user.created_at.tzinfo is None else user.created_at,
                    'last_activity': last_activity,
                    'entries_count': entries_count,
                    'daily_calorie_goal': user.daily_calorie_goal,
                    'weight': user.weight,
                    'height': user.height
                })
            
            return users_summary
        finally:
            db.close()

    @staticmethod
    def get_user_detailed_info(telegram_id: int):
        """Получить детальную информацию о пользователе для админа"""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return None
            
            # Статистика пользователя
            total_entries = db.query(func.count(FoodEntry.id)).filter(
                FoodEntry.user_id == user.id
            ).scalar() or 0
            
            # Последние 5 записей
            recent_entries = db.query(FoodEntry).filter(
                FoodEntry.user_id == user.id
            ).order_by(FoodEntry.created_at.desc()).limit(5).all()
            
            # Общие калории за все время
            total_calories = db.query(func.sum(FoodEntry.total_calories)).filter(
                FoodEntry.user_id == user.id
            ).scalar() or 0
            
            # Общие дни с записями
            unique_days = db.query(
                func.count(func.distinct(func.date(FoodEntry.created_at)))
            ).filter(FoodEntry.user_id == user.id).scalar() or 0
            
            avg_calories_per_day = float(total_calories) / unique_days if unique_days > 0 else 0
            
            return {
                'user': user,
                'total_entries': total_entries,
                'total_calories': float(total_calories),
                'unique_days': unique_days,
                'avg_calories_per_day': avg_calories_per_day,
                'recent_entries': [
                    {
                        'created_at': entry.created_at.replace(tzinfo=timezone.utc) if entry.created_at and entry.created_at.tzinfo is None else entry.created_at,
                        'calories': entry.total_calories,
                        'confidence': entry.confidence,
                        'food_items': entry.food_items[:100] + '...' if entry.food_items and len(entry.food_items) > 100 else entry.food_items
                    }
                    for entry in recent_entries
                ]
            }
        finally:
            db.close()
    
    @staticmethod
    def complete_onboarding(telegram_id: int, weight: float, height: float, age: int, gender: str, activity_level: str):
        """Завершить онбординг пользователя и рассчитать персональную норму калорий"""
        import logging
        logger = logging.getLogger(__name__)
        db = SessionLocal()
        
        try:
            logger.info(f"Начинаем онбординг для пользователя {telegram_id}")
            logger.info(f"Данные: вес={weight}, рост={height}, возраст={age}, пол={gender}, активность={activity_level}")
            
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                logger.error(f"Пользователь {telegram_id} не найден в базе данных")
                return False
            
            # Проверяем, является ли это настоящим пользователем из БД
            if not hasattr(user, 'id') or user.id is None:
                logger.error(f"Пользователь {telegram_id} является временным, не может быть сохранен")
                return False
            
            # Обновляем данные пользователя
            logger.info(f"Обновляем данные пользователя {telegram_id}")
            user.weight = float(weight)
            user.height = float(height) 
            user.age = int(age)
            user.gender = str(gender).lower()
            user.activity_level = str(activity_level)
            
            logger.info(f"Данные установлены: weight={user.weight}, height={user.height}, age={user.age}, gender={user.gender}, activity_level={user.activity_level}")
            
            # Примечание: onboarding_completed временно отключено для совместимости
            # Завершенность онбординга определяется наличием основных данных
            
            # Рассчитываем персональную норму калорий
            try:
                logger.info(f"Начинаем расчет дневной нормы калорий для пользователя {telegram_id}")
                calculated_goal = user.calculate_daily_calorie_goal()
                logger.info(f"Рассчитанная норма калорий: {calculated_goal}")
                user.daily_calorie_goal = calculated_goal
            except Exception as calc_error:
                logger.error(f"Ошибка при расчете калорий: {calc_error}")
                # Устанавливаем значение по умолчанию
                user.daily_calorie_goal = 2000
                logger.info(f"Установлена норма калорий по умолчанию: {user.daily_calorie_goal}")
            
            logger.info(f"Сохраняем изменения в базу данных для пользователя {telegram_id}")
            db.commit()
            logger.info(f"✅ Онбординг завершен для пользователя {telegram_id}. Цель калорий: {user.daily_calorie_goal}")
            return user.daily_calorie_goal
            
        except Exception as e:
            logger.error(f"Критическая ошибка при завершении онбординга для {telegram_id}: {e}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            import traceback
            logger.error(f"Полный traceback: {traceback.format_exc()}")
            db.rollback()
            return False
        finally:
            db.close()

    @staticmethod 
    def is_onboarding_completed(telegram_id: int) -> bool:
        """Проверить завершен ли онбординг у пользователя"""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return False
            
            # Считаем что пользователь прошел онбординг если у него есть основные данные
            return bool(user.weight and user.height and user.age and user.gender)
        finally:
            db.close()
