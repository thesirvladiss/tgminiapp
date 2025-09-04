const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');

const userSchema = new mongoose.Schema({
    // Telegram данные
    telegramId: {
        type: Number,
        required: true,
        unique: true,
        index: true
    },

    username: {
        type: String,
        trim: true
    },

    firstName: {
        type: String,
        required: true
    },

    lastName: {
        type: String
    },

    // Статус пользователя
    isActive: {
        type: Boolean,
        default: true
    },

    // Подписка
    subscription: {
        isActive: {
            type: Boolean,
            default: false
        },
        startDate: Date,
        endDate: Date,
        type: {
            type: String,
            enum: ['monthly', 'yearly'],
            default: 'monthly'
        },
        autoRenew: {
            type: Boolean,
            default: false
        }
    },

    // Покупки
    purchases: [{
        podcastId: {
            type: mongoose.Schema.Types.ObjectId,
            ref: 'Podcast'
        },
        purchaseDate: {
            type: Date,
            default: Date.now
        },
        amount: {
            type: Number,
            required: true
        },
        currency: {
            type: String,
            default: 'RUB'
        },
        status: {
            type: String,
            enum: ['pending', 'completed', 'failed', 'refunded'],
            default: 'pending'
        }
    }],

    // Бесплатный подкаст
    freePodcast: {
        podcastId: {
            type: mongoose.Schema.Types.ObjectId,
            ref: 'Podcast'
        },
        usedAt: Date
    },

    // Статистика прослушивания
    listeningStats: {
        totalTime: {
            type: Number,
            default: 0 // в секундах
        },
        podcastsListened: [{
            podcastId: {
                type: mongoose.Schema.Types.ObjectId,
                ref: 'Podcast'
            },
            listenCount: {
                type: Number,
                default: 0
            },
            totalTime: {
                type: Number,
                default: 0
            },
            lastListened: Date
        }]
    },

    // Настройки уведомлений
    notifications: {
        email: {
            type: Boolean,
            default: true
        },
        telegram: {
            type: Boolean,
            default: true
        },
        push: {
            type: Boolean,
            default: true
        }
    },

    // Метаданные
    lastSeen: {
        type: Date,
        default: Date.now
    },

    registrationDate: {
        type: Date,
        default: Date.now
    },

    // Админ права
    isAdmin: {
        type: Boolean,
        default: false
    },

    // Аналитика
    analytics: {
        source: String, // откуда пришел пользователь
        campaign: String, // рекламная кампания
        referrer: String, // реферер
        device: String, // устройство
        platform: String // платформа
    }
}, {
    timestamps: true
});

// Индексы для быстрого поиска
userSchema.index({ 'subscription.endDate': 1 });
userSchema.index({ 'purchases.status': 1 });
userSchema.index({ 'listeningStats.totalTime': -1 });
userSchema.index({ createdAt: -1 });

// Виртуальные поля
userSchema.virtual('totalSpent').get(function () {
    return this.purchases
        .filter(p => p.status === 'completed')
        .reduce((sum, p) => sum + p.amount, 0);
});

userSchema.virtual('hasActiveSubscription').get(function () {
    if (!this.subscription.isActive) return false;
    return this.subscription.endDate > new Date();
});

userSchema.virtual('subscriptionDaysLeft').get(function () {
    if (!this.hasActiveSubscription) return 0;
    const now = new Date();
    const end = this.subscription.endDate;
    return Math.ceil((end - now) / (1000 * 60 * 60 * 24));
});

// Методы
userSchema.methods.hasAccessToPodcast = function (podcastId) {
    // Проверяем подписку
    if (this.hasActiveSubscription) return true;

    // Проверяем покупки
    const hasPurchased = this.purchases.some(p =>
        p.podcastId.toString() === podcastId.toString() &&
        p.status === 'completed'
    );

    if (hasPurchased) return true;

    // Проверяем бесплатный подкаст
    if (this.freePodcast.podcastId &&
        this.freePodcast.podcastId.toString() === podcastId.toString()) {
        return true;
    }

    return false;
};

userSchema.methods.useFreePodcast = function (podcastId) {
    if (this.freePodcast.podcastId) {
        throw new Error('Бесплатный подкаст уже использован');
    }

    this.freePodcast = {
        podcastId,
        usedAt: new Date()
    };

    return this.save();
};

userSchema.methods.addPurchase = function (podcastId, amount, currency = 'RUB') {
    this.purchases.push({
        podcastId,
        amount,
        currency,
        status: 'pending'
    });

    return this.save();
};

userSchema.methods.updateListeningStats = function (podcastId, listenTime) {
    const existingStat = this.listeningStats.podcastsListened.find(
        stat => stat.podcastId.toString() === podcastId.toString()
    );

    if (existingStat) {
        existingStat.listenCount += 1;
        existingStat.totalTime += listenTime;
        existingStat.lastListened = new Date();
    } else {
        this.listeningStats.podcastsListened.push({
            podcastId,
            listenCount: 1,
            totalTime: listenTime,
            lastListened: new Date()
        });
    }

    this.listeningStats.totalTime += listenTime;
    this.lastSeen = new Date();

    return this.save();
};

// Middleware
userSchema.pre('save', function (next) {
    if (this.isModified('subscription.endDate')) {
        this.subscription.isActive = this.subscription.endDate > new Date();
    }
    next();
});

module.exports = mongoose.model('User', userSchema);
