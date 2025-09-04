# Настройка переменных окружения (.env)

## Создание файла .env

1. В директории `backend/` создайте файл `.env`
2. Скопируйте содержимое ниже в этот файл
3. Заполните все необходимые значения

## Содержимое файла .env

```bash
# ========================================
# Telegram Mini App Backend - Environment Variables
# ========================================

# Основные настройки приложения
NODE_ENV=development
PORT=5000
FRONTEND_URL=http://localhost:3000

# База данных MongoDB
MONGODB_URI=mongodb://admin:password123@localhost:27017/telegram-miniapp?authSource=admin

# JWT секрет для токенов (ИЗМЕНИТЬ В ПРОДАКШЕНЕ!)
JWT_SECRET=your-super-secret-jwt-key-here-change-this-in-production
JWT_EXPIRES_IN=7d

# Telegram Bot API (заполните своим токеном)
TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here

# Email настройки (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
EMAIL_FROM=noreply@yourdomain.com

# Redis (для кэширования и сессий)
REDIS_URL=redis://localhost:6379

# Логирование
LOG_LEVEL=info

# Безопасность
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100

# Файлы
MAX_FILE_SIZE=10485760
UPLOAD_PATH=./uploads

# Аналитика
ANALYTICS_RETENTION_DAYS=365
ANALYTICS_CLEANUP_INTERVAL=86400000

# Уведомления
NOTIFICATIONS_BATCH_SIZE=100
NOTIFICATIONS_RETRY_DELAY=300000

# Платежи
PAYMENT_PROVIDER=test
PAYMENT_WEBHOOK_SECRET=your-webhook-secret

# Мониторинг
ENABLE_METRICS=true
METRICS_PORT=9090
```

## Обязательные настройки

### 1. TELEGRAM_BOT_TOKEN

- Получите у [@BotFather](https://t.me/BotFather) в Telegram
- Создайте нового бота командой `/newbot`
- Скопируйте полученный токен

### 2. JWT_SECRET

- Сгенерируйте случайную строку (минимум 32 символа)
- Можно использовать: `openssl rand -base64 32`
- **ВАЖНО**: Измените в продакшене!

### 3. MONGODB_URI

- Для локальной разработки оставьте как есть
- Для продакшена укажите реальный URI MongoDB

## Опциональные настройки

### Email уведомления

Если нужны email уведомления:

1. Настройте SMTP сервер
2. Заполните SMTP\_\* переменные
3. Укажите реальный email в EMAIL_FROM

### Redis

Для продакшена:

- Укажите реальный Redis сервер
- Настройте пароль если требуется

### Мониторинг

- ENABLE_METRICS=true - включает метрики Prometheus
- METRICS_PORT=9090 - порт для метрик

## Проверка настроек

После создания .env файла:

1. Установите зависимости: `npm install`
2. Запустите сервер: `npm run dev`
3. Проверьте подключение к базе данных
4. Проверьте логи на наличие ошибок

## Безопасность

- **НИКОГДА** не коммитьте .env файл в git
- Добавьте .env в .gitignore
- В продакшене используйте переменные окружения сервера
- Регулярно меняйте JWT_SECRET
- Ограничьте доступ к .env файлу
