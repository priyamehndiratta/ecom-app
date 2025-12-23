# Dockerfile
FROM python:3.11

WORKDIR /app

# Install dependencies at build time
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Ensure Python logs flush immediately
ENV PYTHONUNBUFFERED=1

# Expose Flask port
EXPOSE 5000

# Initialize DB and run app when container starts
CMD ["sh", "-c", "python init_db.py && python application.py"]
