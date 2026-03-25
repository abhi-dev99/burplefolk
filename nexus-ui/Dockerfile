FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build


FROM nginx:1.27-alpine
# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy nginx config FIRST (before dist files)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Set permissions that work with nginx user (nginx uid 101)
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html && \
    chmod 755 /etc/nginx/conf.d/default.conf && \
    chmod 755 /etc/nginx/conf.d


EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]

