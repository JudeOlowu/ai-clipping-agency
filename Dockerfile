FROM python:3.11-slim

# Install system dependencies (FFmpeg, OpenCV dependencies, ImageMagick, Node.js)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    imagemagick \
    curl \
    supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Fix ImageMagick policy to allow text rendering for MoviePy
RUN sed -i 's/rights="none" pattern="path"/rights="read|write" pattern="path"/g' /etc/ImageMagick-6/policy.xml || true

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend
COPY . .

# Build the frontend
WORKDIR /app/dashboard/frontend
RUN npm install
RUN npm run build

# Configure supervisord
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8000

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
