FROM node:18-alpine

# Set working directory
WORKDIR /app

# Copy package files from frontend directory (context is repo root)
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy frontend source code (context is repo root)
COPY frontend/ .
RUN rm -rf node_modules

# Debug: List files to verify lib directory exists
RUN ls -la src/
RUN ls -la src/lib/ || echo "lib directory not found!"

RUN npm install

# Build the application with environment variables
ARG VITE_API_BASE_URL
ARG VITE_WS_BASE_URL
ARG VITE_APP_NAME
ARG VITE_APP_VERSION
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_WS_BASE_URL=$VITE_WS_BASE_URL
ENV VITE_APP_NAME=$VITE_APP_NAME
ENV VITE_APP_VERSION=$VITE_APP_VERSION
RUN npm run build

# Expose port
EXPOSE 80

# Start the application
CMD ["node", "serve.js"]
