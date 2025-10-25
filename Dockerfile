# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all necessary application files
COPY app.py .
COPY live_control.py .
COPY local_application/ local_application/
COPY templates/ templates/
COPY static/ static/
COPY data/ data/

# Expose port
EXPOSE 8000

# Start Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", 'app:create_app()', "--timeout", "120", "--access-logfile", "-", "app:app"]
 