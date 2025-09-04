const mongoose = require('mongoose');

const podcastSchema = new mongoose.Schema({
  // Основная информация
  title: {
    type: String,
    required: true,
    trim: true,
    maxlength: 200
  },
  
  description: {
    type: String,
    required: true,
    maxlength: 2000
  },
  
  // Категория и теги
  category: {
    type: String,
    required: true,
    enum: ['финансы', 'отношения', 'психология', 'медитация', 'развитие', 'здоровье', 'бизнес']
  },
  
  tags: [{
    type: String,
    trim: true,
    maxlength: 50
  }],
  
  // Медиа файлы
  audio: {
    preview: {
      url: String,
      duration: Number, // в секундах
      size: Number // в байтах
    },
    full: {
      url: String,
      duration: Number, // в секундах
      size: Number // в байтах
    }
  },
  
  cover: {
    url: String,
    alt: String
  },
  
  // Статус и публикация
  status: {
    type: String,
    enum: ['draft', 'published', 'archived'],
    default: 'draft'
  },
  
  publishedAt: Date,
  
  // Статистика
  stats: {
    views: {
      type: Number,
      default: 0
    },
    listens: {
      type: Number,
      default: 0
    },
    totalListenTime: {
      type: Number,
      default: 0 // в секундах
    },
    uniqueListeners: {
      type: Number,
      default: 0
    },
    purchases: {
      type: Number,
      default: 0
    },
    revenue: {
      type: Number,
      default: 0 // в копейках
    }
  },
  
  // Цена и доступ
  pricing: {
    isFree: {
      type: Boolean,
      default: false
    },
    price: {
      type: Number,
      default: 20000 // в копейках (200 рублей)
    },
    currency: {
      type: String,
      default: 'RUB'
    },
    discount: {
      type: Number,
      default: 0 // процент скидки
    },
    discountEndDate: Date
  },
  
  // SEO и метаданные
  seo: {
    slug: {
      type: String,
      unique: true,
      sparse: true
    },
    metaTitle: String,
    metaDescription: String,
    keywords: [String]
  },
  
  // Автор и права
  author: {
    name: {
      type: String,
      default: 'Петр Лупенко'
    },
    bio: String,
    avatar: String
  },
  
  // Дополнительная информация
  transcript: String, // расшифровка подкаста
  notes: String, // заметки для слушателей
  resources: [{
    title: String,
    url: String,
    type: String // 'link', 'pdf', 'video'
  }],
  
  // Настройки воспроизведения
  playback: {
    allowPreview: {
      type: Boolean,
      default: true
    },
    previewDuration: {
      type: Number,
      default: 300 // 5 минут в секундах
    },
    allowDownload: {
      type: Boolean,
      default: false
    }
  },
  
  // Аналитика
  analytics: {
    source: String, // откуда загружен подкаст
    uploadDate: {
      type: Date,
      default: Date.now
    },
    lastModified: {
      type: Date,
      default: Date.now
    }
  }
}, {
  timestamps: true
});

// Индексы для быстрого поиска
podcastSchema.index({ status: 1, publishedAt: -1 });
podcastSchema.index({ category: 1, status: 1 });
podcastSchema.index({ 'stats.views': -1 });
podcastSchema.index({ 'stats.listens': -1 });
podcastSchema.index({ 'pricing.price': 1 });
podcastSchema.index({ tags: 1 });
podcastSchema.index({ 'seo.slug': 1 });

// Виртуальные поля
podcastSchema.virtual('currentPrice').get(function() {
  if (this.pricing.isFree) return 0;
  
  let price = this.pricing.price;
  
  if (this.pricing.discount > 0 && 
      (!this.pricing.discountEndDate || this.pricing.discountEndDate > new Date())) {
    price = price * (1 - this.pricing.discount / 100);
  }
  
  return Math.round(price);
});

podcastSchema.virtual('formattedPrice').get(function() {
  const price = this.currentPrice / 100; // конвертируем в рубли
  return `${price} ₽`;
});

podcastSchema.virtual('durationFormatted').get(function() {
  const duration = this.audio.full?.duration || 0;
  const hours = Math.floor(duration / 3600);
  const minutes = Math.floor((duration % 3600) / 60);
  
  if (hours > 0) {
    return `${hours}ч ${minutes}м`;
  }
  return `${minutes}м`;
});

podcastSchema.virtual('isPublished').get(function() {
  return this.status === 'published' && 
         this.publishedAt && 
         this.publishedAt <= new Date();
});

// Методы
podcastSchema.methods.incrementViews = function() {
  this.stats.views += 1;
  return this.save();
};

podcastSchema.methods.incrementListens = function(listenTime = 0) {
  this.stats.listens += 1;
  this.stats.totalListenTime += listenTime;
  return this.save();
};

podcastSchema.methods.addPurchase = function(amount) {
  this.stats.purchases += 1;
  this.stats.revenue += amount;
  return this.save();
};

podcastSchema.methods.publish = function() {
  this.status = 'published';
  this.publishedAt = new Date();
  return this.save();
};

podcastSchema.methods.archive = function() {
  this.status = 'archived';
  return this.save();
};

podcastSchema.methods.generateSlug = function() {
  if (this.seo.slug) return this.seo.slug;
  
  let slug = this.title
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
  
  // Добавляем уникальный идентификатор
  slug += `-${Date.now().toString(36)}`;
  
  this.seo.slug = slug;
  return slug;
};

// Middleware
podcastSchema.pre('save', function(next) {
  if (this.isModified('title') || this.isModified('description')) {
    this.analytics.lastModified = new Date();
  }
  
  if (this.isModified('status') && this.status === 'published' && !this.publishedAt) {
    this.publishedAt = new Date();
  }
  
  next();
});

// Статические методы
podcastSchema.statics.findPublished = function() {
  return this.find({
    status: 'published',
    publishedAt: { $lte: new Date() }
  }).sort({ publishedAt: -1 });
};

podcastSchema.statics.findByCategory = function(category) {
  return this.find({
    category,
    status: 'published',
    publishedAt: { $lte: new Date() }
  }).sort({ publishedAt: -1 });
};

podcastSchema.statics.findPopular = function(limit = 10) {
  return this.find({
    status: 'published',
    publishedAt: { $lte: new Date() }
  })
  .sort({ 'stats.listens': -1, 'stats.views': -1 })
  .limit(limit);
};

podcastSchema.statics.findRecent = function(limit = 10) {
  return this.find({
    status: 'published',
    publishedAt: { $lte: new Date() }
  })
  .sort({ publishedAt: -1 })
  .limit(limit);
};

module.exports = mongoose.model('Podcast', podcastSchema);
