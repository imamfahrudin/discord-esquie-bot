# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables for proper logging in Docker
ENV PYTHONUNBUFFERED=1

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY bot.py .

# Copy the package directory so the esquie_bot package is available in the image
COPY esquie_bot ./esquie_bot

# Copy environment file (will be overridden by docker-compose)
COPY .env* ./

# Run the bot
CMD ["python", "bot.py"]