const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
require('dotenv').config();

const connectDB = require('./config/database');
const logger = require('./utils/logger');
const errorHandler = require('./middleware/errorHandler');
const authMiddleware = require('./middleware/auth');

// Импорт роутов
const authRoutes = require('./routes/auth');
const projectRoutes = require('./routes/projects');
const podcastRoutes = require('./routes/podcasts');
const userRoutes = require('./routes/users');
const analyticsRoutes = require('./routes/analytics');
const notificationRoutes = require('./routes/notifications');
const paymentRoutes = require('./routes/payments');

const app = express();
const PORT = process.env.PORT || 5000;

// Подключение к базе данных
connectDB();

// Middleware безопасности
app.use(helmet());
app.use(compression());

// CORS настройки
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:3000',
  credentials: true
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 минут
  max: 100, // максимум 100 запросов с одного IP
  message: 'Слишком много запросов с этого IP, попробуйте позже'
});
app.use('/api/', limiter);

// Логирование
app.use(morgan('combined', { stream: { write: message => logger.info(message.trim()) } }));

// Парсинг JSON
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Статические файлы
app.use('/uploads', express.static('uploads'));

// API роуты
app.use('/api/auth', authRoutes);
app.use('/api/projects', authMiddleware, projectRoutes);
app.use('/api/podcasts', authMiddleware, podcastRoutes);
app.use('/api/users', authMiddleware, userRoutes);
app.use('/api/analytics', authMiddleware, analyticsRoutes);
app.use('/api/notifications', authMiddleware, notificationRoutes);
app.use('/api/payments', paymentRoutes);

// Health check
app.get('/health', (req, res) => {
  res.status(200).json({ 
    status: 'OK', 
    timestamp: new Date().toISOString(),
    uptime: process.uptime()
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({ message: 'Маршрут не найден' });
});

// Error handler
app.use(errorHandler);

// Запуск сервера
app.listen(PORT, () => {
  logger.info(`🚀 Сервер запущен на порту ${PORT}`);
  logger.info(`📱 Telegram Mini App Backend готов к работе`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM получен, закрываем сервер...');
  process.exit(0);
});

process.on('SIGINT', () => {
  logger.info('SIGINT получен, закрываем сервер...');
  process.exit(0);
});

module.exports = app;
