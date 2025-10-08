FROM node:18-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code (excluding node_modules)
COPY . .
RUN rm -rf node_modules

# Debug: List files to verify lib directory exists
RUN ls -la src/
RUN ls -la src/lib/ || echo "lib directory not found!"

RUN npm install

# Build the application
RUN npm run build

# Expose port
EXPOSE 80

# Start the application
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "80"]
