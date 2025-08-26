# Use official Python image
FROM python:3.11

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies needed for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    libx11-dev \
    libxcomposite-dev \
    libxrandr-dev \
    libgtk-3-0 \
    libgbm-dev \
    libasound2 \
    libnss3 \
    libxtst6 \
    libxss1 \
    libappindicator3-1 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright and its dependencies
RUN pip install --upgrade pip
RUN pip install playwright

# Copy only the requirements file first to take advantage of Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install discord.py

# Install Playwright browsers
RUN python -m playwright install

# Copy all bot files to the container
COPY . .

# Run the bot
CMD ["python", "bot.py"]