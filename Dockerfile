# Slim image to reduce the size of the container.
FROM python:3.12-slim

# PYTHONUNBUFFERED to reach app logs to docker logs immediately.
# Stops Python creating __pycache__/*.pyc files in the container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first to leverage Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0

# Copy the rest of the application code.
COPY counter/ ./counter/

# CountDetectedObjects writes debug JPEGs.
# So directory has to exist and be writable by the app user.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/tmp/debug \
    && chown -R appuser:appuser /app
USER appuser

# Expose port 5000 for the Flask app.
EXPOSE 5000

# Gunicorn is a production WSGI server. The `--timeout` option is set to 120 seconds.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", \
     "counter.entrypoints.webapp:create_app()"]
