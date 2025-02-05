# Use official Python image
FROM python:3.11

# Set the working directory inside the container
WORKDIR /app

# Copy all bot files to the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install discord.py

# Run the bot
CMD ["python", "bot3.py"]