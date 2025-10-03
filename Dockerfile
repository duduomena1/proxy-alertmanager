
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY discord_proxy.py .

EXPOSE 5001

ENV FLASK_APP=discord_proxy.py
ENV PYTHONPATH=/app

RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser
CMD ["python", "discord_proxy.py"]