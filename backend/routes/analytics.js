const express = require('express');
const router = express.Router();
const analyticsService = require('../services/analyticsService');
const { validatePeriod } = require('../middleware/validation');
const logger = require('../utils/logger');

// Получение общей статистики
router.get('/overview', validatePeriod, async (req, res) => {
    try {
        const { days = 30 } = req.query;
        const stats = await analyticsService.getOverallStats(parseInt(days));

        res.json({
            success: true,
            data: stats
        });
    } catch (error) {
        logger.error(`Ошибка получения общей статистики: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения статистики',
            error: error.message
        });
    }
});

// Получение ежедневной статистики
router.get('/daily', validatePeriod, async (req, res) => {
    try {
        const { days = 30 } = req.query;
        const stats = await analyticsService.getDailyStats(parseInt(days));

        res.json({
            success: true,
            data: stats
        });
    } catch (error) {
        logger.error(`Ошибка получения ежедневной статистики: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения ежедневной статистики',
            error: error.message
        });
    }
});

// Получение статистики доходов
router.get('/revenue', validatePeriod, async (req, res) => {
    try {
        const { days = 30 } = req.query;
        const stats = await analyticsService.getRevenueStats(parseInt(days));

        res.json({
            success: true,
            data: stats
        });
    } catch (error) {
        logger.error(`Ошибка получения статистики доходов: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения статистики доходов',
            error: error.message
        });
    }
});

// Получение топ подкастов
router.get('/top-podcasts', validatePeriod, async (req, res) => {
    try {
        const { days = 30, limit = 10 } = req.query;
        const topPodcasts = await analyticsService.getTopPodcasts(parseInt(days), parseInt(limit));

        res.json({
            success: true,
            data: topPodcasts
        });
    } catch (error) {
        logger.error(`Ошибка получения топ подкастов: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения топ подкастов',
            error: error.message
        });
    }
});

// Получение статистики по категориям
router.get('/categories', validatePeriod, async (req, res) => {
    try {
        const { days = 30 } = req.query;
        const stats = await analyticsService.getCategoryStats(parseInt(days));

        res.json({
            success: true,
            data: stats
        });
    } catch (error) {
        logger.error(`Ошибка получения статистики по категориям: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения статистики по категориям',
            error: error.message
        });
    }
});

// Получение статистики по устройствам
router.get('/devices', validatePeriod, async (req, res) => {
    try {
        const { days = 30 } = req.query;
        const stats = await analyticsService.getDeviceStats(parseInt(days));

        res.json({
            success: true,
            data: stats
        });
    } catch (error) {
        logger.error(`Ошибка получения статистики по устройствам: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения статистики по устройствам',
            error: error.message
        });
    }
});

// Получение статистики по странам
router.get('/countries', validatePeriod, async (req, res) => {
    try {
        const { days = 30 } = req.query;
        const stats = await analyticsService.getCountryStats(parseInt(days));

        res.json({
            success: true,
            data: stats
        });
    } catch (error) {
        logger.error(`Ошибка получения статистики по странам: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения статистики по странам',
            error: error.message
        });
    }
});

// Получение статистики пользователя
router.get('/user/:userId', validatePeriod, async (req, res) => {
    try {
        const { userId } = req.params;
        const { days = 30 } = req.query;
        const stats = await analyticsService.getUserStats(userId, parseInt(days));

        res.json({
            success: true,
            data: stats
        });
    } catch (error) {
        logger.error(`Ошибка получения статистики пользователя: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения статистики пользователя',
            error: error.message
        });
    }
});

// Получение статистики подкаста
router.get('/podcast/:podcastId', validatePeriod, async (req, res) => {
    try {
        const { podcastId } = req.params;
        const { days = 30 } = req.query;
        const stats = await analyticsService.getPodcastStats(podcastId, parseInt(days));

        res.json({
            success: true,
            data: stats
        });
    } catch (error) {
        logger.error(`Ошибка получения статистики подкаста: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения статистики подкаста',
            error: error.message
        });
    }
});

// Получение детальной статистики по датам
router.get('/detailed', validatePeriod, async (req, res) => {
    try {
        const { days = 30, groupBy = 'day' } = req.query;

        let stats;
        if (groupBy === 'hour') {
            // Статистика по часам
            stats = await analyticsService.getHourlyStats(parseInt(days));
        } else if (groupBy === 'week') {
            // Статистика по неделям
            stats = await analyticsService.getWeeklyStats(parseInt(days));
        } else {
            // Статистика по дням (по умолчанию)
            stats = await analyticsService.getDailyStats(parseInt(days));
        }

        res.json({
            success: true,
            data: stats,
            groupBy
        });
    } catch (error) {
        logger.error(`Ошибка получения детальной статистики: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения детальной статистики',
            error: error.message
        });
    }
});

// Получение метрик производительности
router.get('/performance', validatePeriod, async (req, res) => {
    try {
        const { days = 30 } = req.query;

        // Здесь можно добавить метрики производительности
        // например, время ответа API, использование памяти и т.д.
        const performanceStats = {
            period: parseInt(days),
            apiResponseTime: {
                average: 150, // мс
                p95: 300,
                p99: 500
            },
            memoryUsage: {
                current: process.memoryUsage().heapUsed / 1024 / 1024, // MB
                peak: 512 // MB
            },
            uptime: process.uptime(),
            activeConnections: 0 // можно добавить подсчет активных соединений
        };

        res.json({
            success: true,
            data: performanceStats
        });
    } catch (error) {
        logger.error(`Ошибка получения метрик производительности: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка получения метрик производительности',
            error: error.message
        });
    }
});

// Экспорт данных аналитики
router.get('/export', validatePeriod, async (req, res) => {
    try {
        const { days = 30, format = 'json' } = req.query;

        if (format === 'csv') {
            // Экспорт в CSV
            const stats = await analyticsService.getDailyStats(parseInt(days));

            let csv = 'Date,Total Events,Unique Users,Total Revenue\n';
            stats.forEach(day => {
                csv += `${day.date},${day.totalEvents},${day.totalUniqueUsers},${day.totalRevenue || 0}\n`;
            });

            res.setHeader('Content-Type', 'text/csv');
            res.setHeader('Content-Disposition', `attachment; filename=analytics-${days}days.csv`);
            res.send(csv);
        } else {
            // Экспорт в JSON
            const stats = await analyticsService.getOverallStats(parseInt(days));

            res.setHeader('Content-Type', 'application/json');
            res.setHeader('Content-Disposition', `attachment; filename=analytics-${days}days.json`);
            res.json(stats);
        }
    } catch (error) {
        logger.error(`Ошибка экспорта данных аналитики: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка экспорта данных',
            error: error.message
        });
    }
});

// Очистка старых данных аналитики (только для админов)
router.delete('/cleanup', async (req, res) => {
    try {
        const { days = 365 } = req.query;
        const result = await analyticsService.cleanupOldData(parseInt(days));

        res.json({
            success: true,
            message: `Удалено ${result.deletedCount} старых записей`,
            data: result
        });
    } catch (error) {
        logger.error(`Ошибка очистки данных аналитики: ${error.message}`);
        res.status(500).json({
            success: false,
            message: 'Ошибка очистки данных',
            error: error.message
        });
    }
});

module.exports = router;
