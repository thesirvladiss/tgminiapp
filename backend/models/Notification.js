const mongoose = require('mongoose');

const notificationSchema = new mongoose.Schema({
  // Получатель
  recipient: {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      required: true
    },
    telegramId: {
      type: Number,
      required: true
    }
  },
  
  // Тип уведомления
  type: {
    type: String,
    required: true,
    enum: [
      'welcome',
      'podcast_available',
      'subscription_expiring',
      'subscription_expired',
      'payment_success',
      'payment_failed',
      'new_podcast',
      'discount_offer',
      'reminder',
      'system_alert'
    ]
  },
  
  // Заголовок
  title: {
    type: String,
    required: true,
    maxlength: 100
  },
  
  // Содержание
  content: {
    type: String,
    required: true,
    maxlength: 1000
  },
  
  // Дополнительные данные
  data: {
    podcastId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Podcast'
    },
    amount: Number,
    currency: String,
    actionUrl: String,
    imageUrl: String,
    buttonText: String,
    expiresAt: Date
  },
  
  // Каналы отправки
  channels: {
    telegram: {
      type: Boolean,
      default: true
    },
    email: {
      type: Boolean,
      default: false
    },
    push: {
      type: Boolean,
      default: false
    },
    inApp: {
      type: Boolean,
      default: true
    }
  },
  
  // Статус отправки по каналам
  deliveryStatus: {
    telegram: {
      sent: { type: Boolean, default: false },
      sentAt: Date,
      error: String
    },
    email: {
      sent: { type: Boolean, default: false },
      sentAt: Date,
      error: String
    },
    push: {
      sent: { type: Boolean, default: false },
      sentAt: Date,
      error: String
    },
    inApp: {
      sent: { type: Boolean, default: false },
      sentAt: Date,
      readAt: Date
    }
  },
  
  // Приоритет
  priority: {
    type: String,
    enum: ['low', 'normal', 'high', 'urgent'],
    default: 'normal'
  },
  
  // Статус уведомления
  status: {
    type: String,
    enum: ['pending', 'sending', 'sent', 'failed', 'cancelled'],
    default: 'pending'
  },
  
  // Время отправки
  scheduledAt: {
    type: Date,
    default: Date.now
  },
  
  // Время отправки
  sentAt: Date,
  
  // Время прочтения
  readAt: Date,
  
  // Попытки отправки
  retryCount: {
    type: Number,
    default: 0
  },
  
  // Максимальное количество попыток
  maxRetries: {
    type: Number,
    default: 3
  },
  
  // Метаданные
  metadata: {
    source: String, // откуда создано уведомление
    campaign: String, // рекламная кампания
    template: String, // шаблон уведомления
    language: {
      type: String,
      default: 'ru'
    }
  }
}, {
  timestamps: true
});

// Индексы для быстрого поиска
notificationSchema.index({ 'recipient.userId': 1, status: 1 });
notificationSchema.index({ 'recipient.telegramId': 1, status: 1 });
notificationSchema.index({ type: 1, status: 1 });
notificationSchema.index({ scheduledAt: 1, status: 1 });
notificationSchema.index({ priority: 1, scheduledAt: 1 });
notificationSchema.index({ createdAt: -1 });

// Виртуальные поля
notificationSchema.virtual('isRead').get(function() {
  return !!this.readAt;
});

notificationSchema.virtual('isDelivered').get(function() {
  return this.status === 'sent';
});

notificationSchema.virtual('canRetry').get(function() {
  return this.status === 'failed' && this.retryCount < this.maxRetries;
});

// Методы
notificationSchema.methods.markAsSent = function(channel) {
  if (this.deliveryStatus[channel]) {
    this.deliveryStatus[channel].sent = true;
    this.deliveryStatus[channel].sentAt = new Date();
  }
  
  // Проверяем, все ли каналы отправлены
  const allChannels = Object.keys(this.channels).filter(key => this.channels[key]);
  const sentChannels = Object.keys(this.deliveryStatus).filter(key => 
    this.deliveryStatus[key]?.sent
  );
  
  if (allChannels.length === sentChannels.length) {
    this.status = 'sent';
    this.sentAt = new Date();
  }
  
  return this.save();
};

notificationSchema.methods.markAsFailed = function(channel, error) {
  if (this.deliveryStatus[channel]) {
    this.deliveryStatus[channel].error = error;
  }
  
  this.retryCount += 1;
  
  if (this.retryCount >= this.maxRetries) {
    this.status = 'failed';
  } else {
    this.status = 'pending';
  }
  
  return this.save();
};

notificationSchema.methods.markAsRead = function() {
  this.readAt = new Date();
  if (this.deliveryStatus.inApp) {
    this.deliveryStatus.inApp.readAt = new Date();
  }
  return this.save();
};

notificationSchema.methods.retry = function() {
  this.status = 'pending';
  this.scheduledAt = new Date();
  return this.save();
};

// Статические методы
notificationSchema.statics.findPending = function() {
  return this.find({
    status: 'pending',
    scheduledAt: { $lte: new Date() }
  }).sort({ priority: -1, scheduledAt: 1 });
};

notificationSchema.statics.findByUser = function(userId, limit = 50) {
  return this.find({
    'recipient.userId': userId
  })
  .sort({ createdAt: -1 })
  .limit(limit);
};

notificationSchema.statics.findUnreadByUser = function(userId) {
  return this.find({
    'recipient.userId': userId,
    readAt: { $exists: false }
  }).sort({ createdAt: -1 });
};

notificationSchema.statics.createBulk = function(notifications) {
  return this.insertMany(notifications);
};

notificationSchema.statics.cleanupOld = function(days = 90) {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);
  
  return this.deleteMany({
    createdAt: { $lt: cutoffDate },
    status: { $in: ['sent', 'failed', 'cancelled'] }
  });
};

// Middleware
notificationSchema.pre('save', function(next) {
  if (this.isModified('status') && this.status === 'sent') {
    this.sentAt = new Date();
  }
  next();
});

module.exports = mongoose.model('Notification', notificationSchema);
