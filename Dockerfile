FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies first (separate layer so rebuilds are fast when only code changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Collect static files so they are served correctly
RUN python manage.py collectstatic --noinput

# Run migrations and start the development server on container start.
# For production, replace runserver with gunicorn (see docker-compose.yml comment).
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
