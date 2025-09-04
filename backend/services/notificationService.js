const Telegram = require('telegram');
const nodemailer = require('nodemailer');
const logger = require('../utils/logger');
const Notification = require('../models/Notification');
const User = require('../models/User');

class NotificationService {
    constructor() {
        // Инициализация Telegram бота
        this.telegramBot = new Telegram(process.env.TELEGRAM_BOT_TOKEN);

        // Инициализация email транспорта
        this.emailTransporter = nodemailer.createTransporter({
            host: process.env.SMTP_HOST,
            port: process.env.SMTP_PORT,
            secure: process.env.SMTP_SECURE === 'true',
            auth: {
                user: process.env.SMTP_USER,
                pass: process.env.SMTP_PASS
            }
        });
    }

    // Отправка уведомления через Telegram
    async sendTelegramNotification(notification) {
        try {
            const { telegramId } = notification.recipient;
            const { title, content, data } = notification;

            let message = `*${title}*\n\n${content}`;

            // Добавляем кнопку если есть actionUrl
            if (data?.actionUrl) {
                const keyboard = {
                    inline_keyboard: [[
                        {
                            text: data.buttonText || 'Открыть',
                            url: data.actionUrl
                        }
                    ]]
                };

                await this.telegramBot.api.sendMessage({
                    chat_id: telegramId,
                    text: message,
                    parse_mode: 'Markdown',
                    reply_markup: keyboard
                });
            } else {
                await this.telegramBot.api.sendMessage({
                    chat_id: telegramId,
                    text: message,
                    parse_mode: 'Markdown'
                });
            }

            // Отмечаем как отправленное
            await notification.markAsSent('telegram');
            logger.info(`Telegram уведомление отправлено пользователю ${telegramId}`);

            return true;
        } catch (error) {
            logger.error(`Ошибка отправки Telegram уведомления: ${error.message}`);
            await notification.markAsFailed('telegram', error.message);
            return false;
        }
    }

    // Отправка email уведомления
    async sendEmailNotification(notification) {
        try {
            const user = await User.findById(notification.recipient.userId);
            if (!user || !user.notifications.email) {
                return false;
            }

            const { title, content, data } = notification;

            const mailOptions = {
                from: process.env.EMAIL_FROM,
                to: user.email,
                subject: title,
                html: this.generateEmailTemplate(title, content, data)
            };

            await this.emailTransporter.sendMail(mailOptions);

            // Отмечаем как отправленное
            await notification.markAsSent('email');
            logger.info(`Email уведомление отправлено пользователю ${user.email}`);

            return true;
        } catch (error) {
            logger.error(`Ошибка отправки email уведомления: ${error.message}`);
            await notification.markAsFailed('email', error.message);
            return false;
        }
    }

    // Отправка push уведомления
    async sendPushNotification(notification) {
        try {
            // Здесь будет интеграция с push сервисами (Firebase, OneSignal и т.д.)
            // Пока что просто логируем
            logger.info(`Push уведомление отправлено пользователю ${notification.recipient.userId}`);

            await notification.markAsSent('push');
            return true;
        } catch (error) {
            logger.error(`Ошибка отправки push уведомления: ${error.message}`);
            await notification.markAsFailed('push', error.message);
            return false;
        }
    }

    // Отправка in-app уведомления
    async sendInAppNotification(notification) {
        try {
            // In-app уведомления сохраняются в базе и отображаются в приложении
            await notification.markAsSent('inApp');
            logger.info(`In-app уведомление создано для пользователя ${notification.recipient.userId}`);
            return true;
        } catch (error) {
            logger.error(`Ошибка создания in-app уведомления: ${error.message}`);
            await notification.markAsFailed('inApp', error.message);
            return false;
        }
    }

    // Отправка уведомления по всем каналам
    async sendNotification(notification) {
        try {
            notification.status = 'sending';
            await notification.save();

            const promises = [];

            if (notification.channels.telegram) {
                promises.push(this.sendTelegramNotification(notification));
            }

            if (notification.channels.email) {
                promises.push(this.sendEmailNotification(notification));
            }

            if (notification.channels.push) {
                promises.push(this.sendPushNotification(notification));
            }

            if (notification.channels.inApp) {
                promises.push(this.sendInAppNotification(notification));
            }

            await Promise.allSettled(promises);

            return true;
        } catch (error) {
            logger.error(`Ошибка отправки уведомления: ${error.message}`);
            notification.status = 'failed';
            await notification.save();
            return false;
        }
    }

    // Создание и отправка уведомления
    async createAndSend(notificationData) {
        try {
            const notification = new Notification(notificationData);
            await notification.save();

            // Отправляем асинхронно
            setImmediate(() => this.sendNotification(notification));

            return notification;
        } catch (error) {
            logger.error(`Ошибка создания уведомления: ${error.message}`);
            throw error;
        }
    }

    // Массовая отправка уведомлений
    async sendBulkNotifications(notificationsData) {
        try {
            const notifications = await Notification.createBulk(notificationsData);

            // Отправляем все уведомления асинхронно
            notifications.forEach(notification => {
                setImmediate(() => this.sendNotification(notification));
            });

            logger.info(`Создано ${notifications.length} уведомлений для массовой отправки`);
            return notifications;
        } catch (error) {
            logger.error(`Ошибка массовой отправки уведомлений: ${error.message}`);
            throw error;
        }
    }

    // Отправка приветственного уведомления
    async sendWelcomeNotification(userId, telegramId) {
        const notificationData = {
            recipient: { userId, telegramId },
            type: 'welcome',
            title: 'Добро пожаловать! 🎉',
            content: 'Спасибо, что присоединились к проектам Петра Лупенко! У вас есть бесплатный подкаст для прослушивания.',
            priority: 'high',
            channels: {
                telegram: true,
                inApp: true
            }
        };

        return this.createAndSend(notificationData);
    }

    // Уведомление о новом подкасте
    async sendNewPodcastNotification(userIds, podcastId, podcastTitle) {
        const notificationsData = userIds.map(userId => ({
            recipient: { userId, telegramId: 0 }, // telegramId будет заполнен при отправке
            type: 'new_podcast',
            title: 'Новый подкаст доступен! 🎧',
            content: `Вышел новый подкаст "${podcastTitle}". Слушайте прямо сейчас!`,
            data: {
                podcastId,
                actionUrl: `${process.env.FRONTEND_URL}/podcasts-details.html?id=${podcastId}`,
                buttonText: 'Слушать'
            },
            priority: 'normal',
            channels: {
                telegram: true,
                inApp: true
            }
        }));

        return this.sendBulkNotifications(notificationsData);
    }

    // Уведомление об истечении подписки
    async sendSubscriptionExpiringNotification(userId, telegramId, daysLeft) {
        const notificationData = {
            recipient: { userId, telegramId },
            type: 'subscription_expiring',
            title: 'Подписка истекает ⏰',
            content: `Ваша подписка истекает через ${daysLeft} дней. Продлите её, чтобы не потерять доступ к подкастам.`,
            data: {
                actionUrl: `${process.env.FRONTEND_URL}/checkout.html?type=subscription`,
                buttonText: 'Продлить подписку'
            },
            priority: 'high',
            channels: {
                telegram: true,
                email: true,
                inApp: true
            }
        };

        return this.createAndSend(notificationData);
    }

    // Уведомление об успешной оплате
    async sendPaymentSuccessNotification(userId, telegramId, amount, type) {
        const typeText = type === 'subscription' ? 'подписку' : 'подкаст';
        const notificationData = {
            recipient: { userId, telegramId },
            type: 'payment_success',
            title: 'Оплата прошла успешно! ✅',
            content: `Спасибо за покупку ${typeText} на сумму ${amount} ₽. Доступ открыт!`,
            data: {
                amount,
                currency: 'RUB',
                actionUrl: `${process.env.FRONTEND_URL}/success.html?type=${type}`,
                buttonText: 'Перейти к контенту'
            },
            priority: 'normal',
            channels: {
                telegram: true,
                inApp: true
            }
        };

        return this.createAndSend(notificationData);
    }

    // Генерация HTML шаблона для email
    generateEmailTemplate(title, content, data) {
        return `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">
          <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #422B23; color: white; padding: 20px; text-align: center; }
            .content { padding: 20px; background: #f9f9f9; }
            .button { display: inline-block; padding: 12px 24px; background: #422B23; color: white; text-decoration: none; border-radius: 6px; }
            .footer { text-align: center; padding: 20px; color: #666; font-size: 14px; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>${title}</h1>
            </div>
            <div class="content">
              <p>${content}</p>
              ${data?.actionUrl ? `<p><a href="${data.actionUrl}" class="button">${data.buttonText || 'Открыть'}</a></p>` : ''}
            </div>
            <div class="footer">
              <p>Проекты Петра Лупенко</p>
              <p>Это автоматическое уведомление, не отвечайте на него</p>
            </div>
          </div>
        </body>
      </html>
    `;
    }

    // Обработка всех pending уведомлений
    async processPendingNotifications() {
        try {
            const pendingNotifications = await Notification.findPending();
            logger.info(`Найдено ${pendingNotifications.length} pending уведомлений`);

            for (const notification of pendingNotifications) {
                await this.sendNotification(notification);
                // Небольшая задержка между отправками
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        } catch (error) {
            logger.error(`Ошибка обработки pending уведомлений: ${error.message}`);
        }
    }

    // Очистка старых уведомлений
    async cleanupOldNotifications() {
        try {
            const result = await Notification.cleanupOld();
            logger.info(`Удалено ${result.deletedCount} старых уведомлений`);
        } catch (error) {
            logger.error(`Ошибка очистки старых уведомлений: ${error.message}`);
        }
    }
}

module.exports = new NotificationService();
