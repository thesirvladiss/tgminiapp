# Telegram Mini App Backend

Полноценный бэкенд для Telegram Mini App "Проекты Петра Лупенко" с расширенной аналитикой, уведомлениями и системой управления.

## 🚀 Возможности

### Основной функционал

- **Пользователи**: Регистрация, авторизация, управление профилями
- **Подкасты**: CRUD операции, загрузка файлов, управление статусами
- **Проекты**: Управление карточками проектов
- **Платежи**: Обработка покупок и подписок
- **Аналитика**: Детальная статистика и метрики
- **Уведомления**: Многоканальные уведомления (Telegram, Email, Push, In-App)

### Аналитика и метрики

- Отслеживание пользовательского поведения
- Статистика прослушивания подкастов
- Анализ доходов и транзакций
- Метрики по устройствам и странам
- Экспорт данных в JSON/CSV

### Система уведомлений

- Автоматические уведомления о событиях
- Шаблоны для разных типов уведомлений
- Очередь отправки с повторными попытками
- Поддержка Telegram Bot API

## 🛠 Технологии

- **Node.js** + **Express.js** - веб-сервер
- **MongoDB** + **Mongoose** - база данных
- **JWT** - аутентификация
- **Multer** - загрузка файлов
- **Sharp** - обработка изображений
- **Winston** - логирование
- **Redis** - кэширование
- **Telegram Bot API** - интеграция с Telegram
- **Nodemailer** - отправка email

## 📁 Структура проекта

```
backend/
├── config/           # Конфигурация
│   └── database.js   # Подключение к MongoDB
├── middleware/       # Middleware
│   ├── auth.js       # Аутентификация
│   ├── errorHandler.js # Обработка ошибок
│   └── validation.js # Валидация данных
├── models/           # Модели данных
│   ├── User.js       # Пользователи
│   ├── Podcast.js    # Подкасты
│   ├── Analytics.js  # Аналитика
│   └── Notification.js # Уведомления
├── routes/           # API роуты
│   ├── auth.js       # Аутентификация
│   ├── users.js      # Пользователи
│   ├── podcasts.js   # Подкасты
│   ├── analytics.js  # Аналитика
│   └── notifications.js # Уведомления
├── services/         # Бизнес-логика
│   ├── analyticsService.js # Сервис аналитики
│   └── notificationService.js # Сервис уведомлений
├── utils/            # Утилиты
│   └── logger.js     # Система логирования
├── uploads/          # Загруженные файлы
├── logs/             # Логи приложения
├── server.js         # Основной сервер
├── package.json      # Зависимости
└── README.md         # Документация
```

## 🚀 Установка и запуск

### 1. Клонирование и установка зависимостей

```bash
cd backend
npm install
```

### 2. Настройка окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Заполните необходимые переменные:

```env
NODE_ENV=development
PORT=5000
MONGODB_URI=mongodb://localhost:27017/telegram-miniapp
JWT_SECRET=your-secret-key
TELEGRAM_BOT_TOKEN=your-bot-token
```

### 3. Запуск MongoDB

```bash
# Локально
mongod

# Или через Docker
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### 4. Запуск сервера

```bash
# Режим разработки
npm run dev

# Продакшн
npm start
```

## 📊 API Endpoints

### Аутентификация

- `POST /api/auth/login` - Вход в админку
- `POST /api/auth/register` - Регистрация админа
- `POST /api/auth/telegram` - Авторизация через Telegram

### Пользователи

- `GET /api/users` - Список пользователей
- `GET /api/users/:id` - Информация о пользователе
- `PUT /api/users/:id` - Обновление пользователя
- `DELETE /api/users/:id` - Удаление пользователя

### Подкасты

- `GET /api/podcasts` - Список подкастов
- `POST /api/podcasts` - Создание подкаста
- `GET /api/podcasts/:id` - Информация о подкасте
- `PUT /api/podcasts/:id` - Обновление подкаста
- `DELETE /api/podcasts/:id` - Удаление подкаста
- `POST /api/podcasts/:id/upload` - Загрузка файлов

### Аналитика

- `GET /api/analytics/overview` - Общая статистика
- `GET /api/analytics/daily` - Ежедневная статистика
- `GET /api/analytics/revenue` - Статистика доходов
- `GET /api/analytics/top-podcasts` - Топ подкастов
- `GET /api/analytics/categories` - Статистика по категориям
- `GET /api/analytics/devices` - Статистика по устройствам
- `GET /api/analytics/countries` - Статистика по странам
- `GET /api/analytics/export` - Экспорт данных

### Уведомления

- `GET /api/notifications` - Список уведомлений
- `POST /api/notifications` - Создание уведомления
- `PUT /api/notifications/:id/read` - Отметить как прочитанное
- `POST /api/notifications/bulk` - Массовая отправка

## 🔧 Настройка

### MongoDB

Убедитесь, что MongoDB запущена и доступна по указанному URI.

### Telegram Bot

1. Создайте бота через @BotFather
2. Получите токен и добавьте в `.env`
3. Настройте webhook (если необходимо)

### Email (SMTP)

Для отправки email уведомлений настройте SMTP сервер:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

### Redis (опционально)

Для кэширования и сессий:

```bash
docker run -d -p 6379:6379 --name redis redis:alpine
```

## 📈 Аналитика

### Отслеживаемые события

- Регистрация и вход пользователей
- Просмотр и прослушивание подкастов
- Покупки и подписки
- Ошибки и проблемы
- Технические метрики

### Метрики

- Количество пользователей
- Активность и вовлеченность
- Доходы и конверсия
- Производительность системы
- Географическое распределение

## 🔔 Уведомления

### Типы уведомлений

- **Приветственные** - для новых пользователей
- **Новые подкасты** - уведомления о выходе
- **Подписка** - напоминания об истечении
- **Платежи** - подтверждения и ошибки
- **Системные** - важные обновления

### Каналы доставки

- **Telegram** - через бота
- **Email** - SMTP
- **Push** - мобильные уведомления
- **In-App** - внутри приложения

## 🚧 Разработка

### Структура кода

- **Models** - схемы данных MongoDB
- **Services** - бизнес-логика
- **Routes** - API endpoints
- **Middleware** - промежуточные обработчики

### Логирование

Используется Winston для структурированного логирования:

- Логи ошибок в `logs/error.log`
- Все логи в `logs/combined.log`
- Консольный вывод в режиме разработки

### Обработка ошибок

Централизованная обработка ошибок с детальным логированием.

## 🧪 Тестирование

```bash
# Запуск тестов
npm test

# Тесты с покрытием
npm run test:coverage
```

## 📦 Развертывание

### Docker

```bash
docker build -t telegram-miniapp-backend .
docker run -p 5000:5000 telegram-miniapp-backend
```

### PM2 (продакшн)

```bash
npm install -g pm2
pm2 start server.js --name "telegram-miniapp-backend"
pm2 startup
pm2 save
```

## 🔒 Безопасность

- JWT токены для аутентификации
- Rate limiting для защиты от DDoS
- Валидация входных данных
- Helmet для защиты заголовков
- CORS настройки
- Логирование безопасности

## 📊 Мониторинг

- Health check endpoint `/health`
- Метрики производительности
- Логирование ошибок
- Мониторинг базы данных

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

MIT License

## 📞 Поддержка

При возникновении вопросов обращайтесь к разработчику.
