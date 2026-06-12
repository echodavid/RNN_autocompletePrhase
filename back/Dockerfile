FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY back/requirements.txt /app/back/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r back/requirements.txt torch

COPY back /app/back
COPY model /app/model

WORKDIR /app/back
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
