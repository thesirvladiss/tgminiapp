# Используем официальный Node.js образ
FROM node:18-alpine

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем package.json и package-lock.json
COPY package*.json ./

# Устанавливаем зависимости
RUN npm ci --only=production

# Копируем исходный код
COPY . .

# Создаем директории для логов и загрузок
RUN mkdir -p logs uploads

# Устанавливаем права доступа
RUN chown -R node:node /app
USER node

# Открываем порт
EXPOSE 5000

# Запускаем приложение
CMD ["npm", "start"]
