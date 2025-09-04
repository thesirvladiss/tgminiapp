const mongoose = require('mongoose');
const logger = require('../utils/logger');

const connectDB = async () => {
  try {
    const conn = await mongoose.connect(process.env.MONGODB_URI || 'mongodb://localhost:27017/telegram-miniapp', {
      useNewUrlParser: true,
      useUnifiedTopology: true,
    });

    logger.info(`✅ MongoDB подключена: ${conn.connection.host}`);

    // Обработка ошибок подключения
    mongoose.connection.on('error', (err) => {
      logger.error('❌ Ошибка MongoDB:', err);
    });

    mongoose.connection.on('disconnected', () => {
      logger.warn('⚠️ MongoDB отключена');
    });

    // Graceful shutdown
    process.on('SIGINT', async () => {
      await mongoose.connection.close();
      logger.info('MongoDB соединение закрыто');
      process.exit(0);
    });

  } catch (error) {
    logger.error('❌ Ошибка подключения к MongoDB:', error);
    process.exit(1);
  }
};

module.exports = connectDB;
