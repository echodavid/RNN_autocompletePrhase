FROM node:20-alpine

WORKDIR /app
COPY fron/package*.json ./
RUN npm install --production
COPY fron/ ./

EXPOSE 5500
CMD ["node", "server.js"]
