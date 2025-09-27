# 🚀 Быстрый старт

## 1. Получите необходимые ключи

### Telegram Bot Token
1. Напишите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Выберите имя для бота
4. Скопируйте полученный токен

### OpenAI API Key  
1. Зайдите на [platform.openai.com](https://platform.openai.com)
2. Зарегистрируйтесь или войдите в аккаунт
3. Перейдите в раздел API Keys
4. Создайте новый ключ и скопируйте его

## 2. Настройте проект

Создайте файл `.env` в папке проекта:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_botfather
OPENAI_API_KEY=ваш_ключ_от_openai
DATABASE_URL=sqlite:///calorie_bot.db
BOT_NAME=Калории Бот 🍎
```

## 3. Запустите бота

### Вариант A: Простой запуск
```bash
pip install -r requirements.txt
python bot.py
```

### Вариант B: Через Docker
```bash
chmod +x start.sh
./start.sh start
```

## 4. Протестируйте бота

1. Найдите вашего бота в Telegram
2. Отправьте команду `/start`
3. Отправьте фото еды
4. Получите анализ калорий!

## 🎯 Что дальше?

- Настройте цели калорий в `/settings`
- Посмотрите статистику в `/stats`
- Изучите полную документацию в `README.md`

## 📞 Нужна помощь?

- Прочитайте раздел "Отладка" в README.md
- Проверьте логи: `./start.sh logs`
- Убедитесь, что у вас есть баланс на OpenAI

**Готово! Ваш AI-бот для подсчета калорий работает! 🍎**
