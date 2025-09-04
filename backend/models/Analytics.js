const mongoose = require('mongoose');

const analyticsSchema = new mongoose.Schema({
  // Тип события
  eventType: {
    type: String,
    required: true,
    enum: [
      'user_registration',
      'user_login',
      'podcast_view',
      'podcast_listen',
      'podcast_purchase',
      'subscription_purchase',
      'payment_success',
      'payment_failed',
      'user_logout',
      'app_open',
      'app_close',
      'error_occurred'
    ]
  },

  // Пользователь (если применимо)
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: false
  },

  // Telegram ID пользователя
  telegramId: {
    type: Number,
    required: false
  },

  // Подкаст (если применимо)
  podcastId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Podcast',
    required: false
  },

  // Детали события
  eventData: {
    // Общие данные
    sessionId: String,
    userAgent: String,
    ipAddress: String,

    // Данные о местоположении
    country: String,
    city: String,
    timezone: String,

    // Технические данные
    device: String,
    platform: String,
    browser: String,
    version: String,

    // Пользовательские данные
    referrer: String,
    source: String,
    campaign: String,

    // Специфичные для события данные
    duration: Number, // для прослушивания
    amount: Number, // для покупок
    currency: String,
    paymentMethod: String,
    errorMessage: String, // для ошибок
    pageUrl: String,
    buttonClicked: String
  },

  // Метаданные
  timestamp: {
    type: Date,
    default: Date.now
  },

  // Время выполнения (для API запросов)
  responseTime: Number,

  // Статус события
  status: {
    type: String,
    enum: ['success', 'failed', 'pending'],
    default: 'success'
  }
}, {
  timestamps: true
});

// Индексы для быстрого поиска
analyticsSchema.index({ eventType: 1, timestamp: -1 });
analyticsSchema.index({ userId: 1, timestamp: -1 });
analyticsSchema.index({ podcastId: 1, timestamp: -1 });
analyticsSchema.index({ 'eventData.sessionId': 1 });
analyticsSchema.index({ 'eventData.ipAddress': 1 });
analyticsSchema.index({ 'eventData.country': 1, timestamp: -1 });

// Статические методы для агрегации
analyticsSchema.statics.getUserStats = function (userId, days = 30) {
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - days);

  return this.aggregate([
    {
      $match: {
        userId: mongoose.Types.ObjectId(userId),
        timestamp: { $gte: startDate }
      }
    },
    {
      $group: {
        _id: '$eventType',
        count: { $sum: 1 },
        totalDuration: { $sum: '$eventData.duration' },
        totalAmount: { $sum: '$eventData.amount' }
      }
    }
  ]);
};

analyticsSchema.statics.getPodcastStats = function (podcastId, days = 30) {
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - days);

  return this.aggregate([
    {
      $match: {
        podcastId: mongoose.Types.ObjectId(podcastId),
        timestamp: { $gte: startDate }
      }
    },
    {
      $group: {
        _id: '$eventType',
        count: { $sum: 1 },
        uniqueUsers: { $addToSet: '$userId' },
        totalDuration: { $sum: '$eventData.duration' }
      }
    },
    {
      $project: {
        eventType: '$_id',
        count: 1,
        uniqueUsers: { $size: '$uniqueUsers' },
        totalDuration: 1
      }
    }
  ]);
};

analyticsSchema.statics.getDailyStats = function (days = 30) {
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - days);

  return this.aggregate([
    {
      $match: {
        timestamp: { $gte: startDate }
      }
    },
    {
      $group: {
        _id: {
          date: { $dateToString: { format: '%Y-%m-%d', date: '$timestamp' } },
          eventType: '$eventType'
        },
        count: { $sum: 1 },
        uniqueUsers: { $addToSet: '$userId' },
        totalAmount: { $sum: '$eventData.amount' }
      }
    },
    {
      $group: {
        _id: '$_id.date',
        events: {
          $push: {
            eventType: '$_id.eventType',
            count: '$count',
            uniqueUsers: { $size: '$uniqueUsers' },
            totalAmount: '$totalAmount'
          }
        },
        totalEvents: { $sum: '$count' },
        totalUniqueUsers: { $addToSet: '$uniqueUsers' }
      }
    },
    {
      $project: {
        date: '$_id',
        events: 1,
        totalEvents: 1,
        totalUniqueUsers: { $size: { $reduce: { input: '$totalUniqueUsers', initialValue: [], in: { $concatArrays: ['$$value', '$$this'] } } } }
      }
    },
    {
      $sort: { date: 1 }
    }
  ]);
};

analyticsSchema.statics.getRevenueStats = function (days = 30) {
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - days);

  return this.aggregate([
    {
      $match: {
        eventType: { $in: ['podcast_purchase', 'subscription_purchase'] },
        timestamp: { $gte: startDate },
        status: 'success'
      }
    },
    {
      $group: {
        _id: {
          date: { $dateToString: { format: '%Y-%m-%d', date: '$timestamp' } },
          eventType: '$eventType'
        },
        count: { $sum: 1 },
        totalAmount: { $sum: '$eventData.amount' },
        uniqueUsers: { $addToSet: '$userId' }
      }
    },
    {
      $group: {
        _id: '$_id.date',
        revenue: {
          $push: {
            eventType: '$_id.eventType',
            count: '$count',
            totalAmount: '$totalAmount',
            uniqueUsers: { $size: '$uniqueUsers' }
          }
        },
        totalRevenue: { $sum: '$totalAmount' },
        totalTransactions: { $sum: '$count' }
      }
    },
    {
      $sort: { _id: 1 }
    }
  ]);
};

analyticsSchema.statics.getTopPodcasts = function (days = 30, limit = 10) {
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - days);

  return this.aggregate([
    {
      $match: {
        eventType: { $in: ['podcast_view', 'podcast_listen'] },
        timestamp: { $gte: startDate },
        podcastId: { $exists: true }
      }
    },
    {
      $group: {
        _id: '$podcastId',
        views: {
          $sum: { $cond: [{ $eq: ['$eventType', 'podcast_view'] }, 1, 0] }
        },
        listens: {
          $sum: { $cond: [{ $eq: ['$eventType', 'podcast_listen'] }, 1, 0] }
        },
        uniqueListeners: { $addToSet: '$userId' },
        totalListenTime: { $sum: '$eventData.duration' }
      }
    },
    {
      $lookup: {
        from: 'podcasts',
        localField: '_id',
        foreignField: '_id',
        as: 'podcast'
      }
    },
    {
      $unwind: '$podcast'
    },
    {
      $project: {
        podcastId: '$_id',
        title: '$podcast.title',
        category: '$podcast.category',
        views: 1,
        listens: 1,
        uniqueListeners: { $size: '$uniqueListeners' },
        totalListenTime: 1,
        score: { $add: ['$views', { $multiply: ['$listens', 2] }] }
      }
    },
    {
      $sort: { score: -1 }
    },
    {
      $limit: limit
    }
  ]);
};

// Методы экземпляра
analyticsSchema.methods.addUserData = function (userData) {
  this.eventData = { ...this.eventData, ...userData };
  return this.save();
};

analyticsSchema.methods.markAsFailed = function (errorMessage) {
  this.status = 'failed';
  this.eventData.errorMessage = errorMessage;
  return this.save();
};

module.exports = mongoose.model('Analytics', analyticsSchema);
