"""
Модель базы данных для телеграм-бота подсчета калорий
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import config

Base = declarative_base()

class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
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
    
    # Связи
    food_entries = relationship("FoodEntry", back_populates="user", cascade="all, delete-orphan")
    
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

def create_tables():
    """Создание всех таблиц в базе данных"""
    Base.metadata.create_all(bind=engine)

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
                
                # Логируем создание нового пользователя
                import logging
                logger = logging.getLogger(__name__)
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
                
                # Логируем загрузку существующего пользователя
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Загружен пользователь {telegram_id} с целью {user.daily_calorie_goal} ккал")
                
            return user
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
            # Получаем все записи за день
            entries = db.query(FoodEntry).filter(
                FoodEntry.user_id == user_id,
                FoodEntry.created_at >= datetime.combine(date, datetime.min.time()),
                FoodEntry.created_at < datetime.combine(date, datetime.max.time())
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
            
        finally:
            db.close()
    
    @staticmethod
    def get_user_stats(user_id, days=7):
        """Получить статистику пользователя за последние N дней"""
        db = SessionLocal()
        try:
            from datetime import timedelta
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days-1)
            
            stats = db.query(DailyStats).filter(
                DailyStats.user_id == user_id,
                DailyStats.date >= start_date,
                DailyStats.date <= end_date
            ).order_by(DailyStats.date).all()
            
            return stats
        finally:
            db.close()
    
    @staticmethod
    def get_today_calories(user_id):
        """Получить калории за сегодня - с прямым подсчетом из записей еды"""
        db = SessionLocal()
        try:
            # Используем тот же подход что и в get_user_info
            today = datetime.now(timezone.utc).date()
            today_calories = db.query(func.sum(FoodEntry.total_calories)).filter(
                FoodEntry.user_id == user_id,
                func.date(FoodEntry.created_at) == today
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
            today_calories = db.query(func.sum(FoodEntry.calories)).filter(
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
