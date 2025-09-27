# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем папку для базы данных
RUN mkdir -p /app/data

# Создаем непривилегированного пользователя
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Порт по умолчанию
EXPOSE 8000

# Команда запуска (можно переопределить в docker-compose)
CMD ["python", "bot.py"]
