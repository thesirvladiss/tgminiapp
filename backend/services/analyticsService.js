const Analytics = require('../models/Analytics');
const User = require('../models/User');
const Podcast = require('../models/Podcast');
const logger = require('../utils/logger');

class AnalyticsService {
    // Создание события аналитики
    async trackEvent(eventType, data = {}) {
        try {
            const analyticsData = {
                eventType,
                userId: data.userId,
                telegramId: data.telegramId,
                podcastId: data.podcastId,
                eventData: {
                    sessionId: data.sessionId,
                    userAgent: data.userAgent,
                    ipAddress: data.ipAddress,
                    country: data.country,
                    city: data.city,
                    timezone: data.timezone,
                    device: data.device,
                    platform: data.platform,
                    browser: data.browser,
                    version: data.version,
                    referrer: data.referrer,
                    source: data.source,
                    campaign: data.campaign,
                    duration: data.duration,
                    amount: data.amount,
                    currency: data.currency,
                    paymentMethod: data.paymentMethod,
                    errorMessage: data.errorMessage,
                    pageUrl: data.pageUrl,
                    buttonClicked: data.buttonClicked
                }
            };

            const analytics = new Analytics(analyticsData);
            await analytics.save();

            logger.info(`Событие ${eventType} записано в аналитику`);
            return analytics;
        } catch (error) {
            logger.error(`Ошибка записи события аналитики: ${error.message}`);
            throw error;
        }
    }

    // Отслеживание просмотра подкаста
    async trackPodcastView(podcastId, userId, userData = {}) {
        try {
            // Записываем событие
            await this.trackEvent('podcast_view', {
                podcastId,
                userId,
                ...userData
            });

            // Обновляем статистику подкаста
            await Podcast.findByIdAndUpdate(podcastId, {
                $inc: { 'stats.views': 1 }
            });

            logger.info(`Просмотр подкаста ${podcastId} записан`);
        } catch (error) {
            logger.error(`Ошибка записи просмотра подкаста: ${error.message}`);
        }
    }

    // Отслеживание прослушивания подкаста
    async trackPodcastListen(podcastId, userId, duration, userData = {}) {
        try {
            // Записываем событие
            await this.trackEvent('podcast_listen', {
                podcastId,
                userId,
                duration,
                ...userData
            });

            // Обновляем статистику подкаста
            await Podcast.findByIdAndUpdate(podcastId, {
                $inc: {
                    'stats.listens': 1,
                    'stats.totalListenTime': duration
                }
            });

            // Обновляем статистику пользователя
            await User.findByIdAndUpdate(userId, {
                $inc: { 'listeningStats.totalTime': duration }
            });

            logger.info(`Прослушивание подкаста ${podcastId} записано, длительность: ${duration}с`);
        } catch (error) {
            logger.error(`Ошибка записи прослушивания подкаста: ${error.message}`);
        }
    }

    // Отслеживание покупки подкаста
    async trackPodcastPurchase(podcastId, userId, amount, userData = {}) {
        try {
            // Записываем событие
            await this.trackEvent('podcast_purchase', {
                podcastId,
                userId,
                amount,
                currency: 'RUB',
                ...userData
            });

            // Обновляем статистику подкаста
            await Podcast.findByIdAndUpdate(podcastId, {
                $inc: {
                    'stats.purchases': 1,
                    'stats.revenue': amount
                }
            });

            logger.info(`Покупка подкаста ${podcastId} записана, сумма: ${amount} копеек`);
        } catch (error) {
            logger.error(`Ошибка записи покупки подкаста: ${error.message}`);
        }
    }

    // Отслеживание покупки подписки
    async trackSubscriptionPurchase(userId, amount, userData = {}) {
        try {
            // Записываем событие
            await this.trackEvent('subscription_purchase', {
                userId,
                amount,
                currency: 'RUB',
                ...userData
            });

            logger.info(`Покупка подписки записана, сумма: ${amount} копеек`);
        } catch (error) {
            logger.error(`Ошибка записи покупки подписки: ${error.message}`);
        }
    }

    // Отслеживание успешной оплаты
    async trackPaymentSuccess(userId, amount, type, userData = {}) {
        try {
            await this.trackEvent('payment_success', {
                userId,
                amount,
                currency: 'RUB',
                paymentMethod: type,
                ...userData
            });

            logger.info(`Успешная оплата записана, тип: ${type}, сумма: ${amount} копеек`);
        } catch (error) {
            logger.error(`Ошибка записи успешной оплаты: ${error.message}`);
        }
    }

    // Отслеживание неудачной оплаты
    async trackPaymentFailed(userId, amount, type, errorMessage, userData = {}) {
        try {
            await this.trackEvent('payment_failed', {
                userId,
                amount,
                currency: 'RUB',
                paymentMethod: type,
                errorMessage,
                ...userData
            });

            logger.info(`Неудачная оплата записана, тип: ${type}, сумма: ${amount} копеек`);
        } catch (error) {
            logger.error(`Ошибка записи неудачной оплаты: ${error.message}`);
        }
    }

    // Отслеживание регистрации пользователя
    async trackUserRegistration(userId, telegramId, userData = {}) {
        try {
            await this.trackEvent('user_registration', {
                userId,
                telegramId,
                ...userData
            });

            logger.info(`Регистрация пользователя ${telegramId} записана`);
        } catch (error) {
            logger.error(`Ошибка записи регистрации пользователя: ${error.message}`);
        }
    }

    // Отслеживание входа пользователя
    async trackUserLogin(userId, telegramId, userData = {}) {
        try {
            await this.trackEvent('user_login', {
                userId,
                telegramId,
                ...userData
            });

            logger.info(`Вход пользователя ${telegramId} записан`);
        } catch (error) {
            logger.error(`Ошибка записи входа пользователя: ${error.message}`);
        }
    }

    // Отслеживание ошибок
    async trackError(userId, errorMessage, userData = {}) {
        try {
            await this.trackEvent('error_occurred', {
                userId,
                errorMessage,
                ...userData
            });

            logger.error(`Ошибка записана в аналитику: ${errorMessage}`);
        } catch (error) {
            logger.error(`Ошибка записи ошибки в аналитику: ${error.message}`);
        }
    }

    // Получение статистики пользователя
    async getUserStats(userId, days = 30) {
        try {
            const stats = await Analytics.getUserStats(userId, days);
            return stats;
        } catch (error) {
            logger.error(`Ошибка получения статистики пользователя: ${error.message}`);
            throw error;
        }
    }

    // Получение статистики подкаста
    async getPodcastStats(podcastId, days = 30) {
        try {
            const stats = await Analytics.getPodcastStats(podcastId, days);
            return stats;
        } catch (error) {
            logger.error(`Ошибка получения статистики подкаста: ${error.message}`);
            throw error;
        }
    }

    // Получение ежедневной статистики
    async getDailyStats(days = 30) {
        try {
            const stats = await Analytics.getDailyStats(days);
            return stats;
        } catch (error) {
            logger.error(`Ошибка получения ежедневной статистики: ${error.message}`);
            throw error;
        }
    }

    // Получение статистики доходов
    async getRevenueStats(days = 30) {
        try {
            const stats = await Analytics.getRevenueStats(days);
            return stats;
        } catch (error) {
            logger.error(`Ошибка получения статистики доходов: ${error.message}`);
            throw error;
        }
    }

    // Получение топ подкастов
    async getTopPodcasts(days = 30, limit = 10) {
        try {
            const topPodcasts = await Analytics.getTopPodcasts(days, limit);
            return topPodcasts;
        } catch (error) {
            logger.error(`Ошибка получения топ подкастов: ${error.message}`);
            throw error;
        }
    }

    // Получение общей статистики
    async getOverallStats(days = 30) {
        try {
            const [
                dailyStats,
                revenueStats,
                topPodcasts,
                totalUsers,
                totalPodcasts
            ] = await Promise.all([
                this.getDailyStats(days),
                this.getRevenueStats(days),
                this.getTopPodcasts(days, 5),
                User.countDocuments(),
                Podcast.countDocuments({ status: 'published' })
            ]);

            // Вычисляем общие метрики
            const totalRevenue = revenueStats.reduce((sum, day) => sum + day.totalRevenue, 0);
            const totalTransactions = revenueStats.reduce((sum, day) => sum + day.totalTransactions, 0);

            const totalEvents = dailyStats.reduce((sum, day) => sum + day.totalEvents, 0);
            const totalUniqueUsers = dailyStats.reduce((sum, day) => sum + day.totalUniqueUsers, 0);

            return {
                period: days,
                totalUsers,
                totalPodcasts,
                totalRevenue: totalRevenue / 100, // конвертируем в рубли
                totalTransactions,
                totalEvents,
                totalUniqueUsers,
                averageRevenuePerTransaction: totalTransactions > 0 ? (totalRevenue / 100) / totalTransactions : 0,
                dailyStats,
                revenueStats,
                topPodcasts
            };
        } catch (error) {
            logger.error(`Ошибка получения общей статистики: ${error.message}`);
            throw error;
        }
    }

    // Получение статистики по категориям
    async getCategoryStats(days = 30) {
        try {
            const stats = await Analytics.aggregate([
                {
                    $match: {
                        eventType: { $in: ['podcast_view', 'podcast_listen'] },
                        timestamp: { $gte: new Date(Date.now() - days * 24 * 60 * 60 * 1000) }
                    }
                },
                {
                    $lookup: {
                        from: 'podcasts',
                        localField: 'podcastId',
                        foreignField: '_id',
                        as: 'podcast'
                    }
                },
                {
                    $unwind: '$podcast'
                },
                {
                    $group: {
                        _id: '$podcast.category',
                        views: {
                            $sum: { $cond: [{ $eq: ['$eventType', 'podcast_view'] }, 1, 0] }
                        },
                        listens: {
                            $sum: { $cond: [{ $eq: ['$eventType', 'podcast_listen'] }, 1, 0] }
                        },
                        uniqueUsers: { $addToSet: '$userId' },
                        totalListenTime: { $sum: '$eventData.duration' }
                    }
                },
                {
                    $project: {
                        category: '$_id',
                        views: 1,
                        listens: 1,
                        uniqueUsers: { $size: '$uniqueUsers' },
                        totalListenTime: 1,
                        score: { $add: ['$views', { $multiply: ['$listens', 2] }] }
                    }
                },
                {
                    $sort: { score: -1 }
                }
            ]);

            return stats;
        } catch (error) {
            logger.error(`Ошибка получения статистики по категориям: ${error.message}`);
            throw error;
        }
    }

    // Получение статистики по устройствам
    async getDeviceStats(days = 30) {
        try {
            const stats = await Analytics.aggregate([
                {
                    $match: {
                        timestamp: { $gte: new Date(Date.now() - days * 24 * 60 * 60 * 1000) },
                        'eventData.device': { $exists: true, $ne: null }
                    }
                },
                {
                    $group: {
                        _id: '$eventData.device',
                        count: { $sum: 1 },
                        uniqueUsers: { $addToSet: '$userId' }
                    }
                },
                {
                    $project: {
                        device: '$_id',
                        count: 1,
                        uniqueUsers: { $size: '$uniqueUsers' }
                    }
                },
                {
                    $sort: { count: -1 }
                }
            ]);

            return stats;
        } catch (error) {
            logger.error(`Ошибка получения статистики по устройствам: ${error.message}`);
            throw error;
        }
    }

    // Получение статистики по странам
    async getCountryStats(days = 30) {
        try {
            const stats = await Analytics.aggregate([
                {
                    $match: {
                        timestamp: { $gte: new Date(Date.now() - days * 24 * 60 * 60 * 1000) },
                        'eventData.country': { $exists: true, $ne: null }
                    }
                },
                {
                    $group: {
                        _id: '$eventData.country',
                        count: { $sum: 1 },
                        uniqueUsers: { $addToSet: '$userId' }
                    }
                },
                {
                    $project: {
                        country: '$_id',
                        count: 1,
                        uniqueUsers: { $size: '$uniqueUsers' }
                    }
                },
                {
                    $sort: { count: -1 }
                }
            ]);

            return stats;
        } catch (error) {
            logger.error(`Ошибка получения статистики по странам: ${error.message}`);
            throw error;
        }
    }

    // Очистка старых данных аналитики
    async cleanupOldData(days = 365) {
        try {
            const cutoffDate = new Date();
            cutoffDate.setDate(cutoffDate.getDate() - days);

            const result = await Analytics.deleteMany({
                timestamp: { $lt: cutoffDate }
            });

            logger.info(`Удалено ${result.deletedCount} старых записей аналитики`);
            return result;
        } catch (error) {
            logger.error(`Ошибка очистки старых данных аналитики: ${error.message}`);
            throw error;
        }
    }
}

module.exports = new AnalyticsService();
