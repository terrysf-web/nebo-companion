FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# tzdata for local time, fonts-nanum covers Korean glyphs in the PDFs
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata fonts-nanum ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .
COPY app ./app

RUN mkdir -p /app/tokens /app/data

EXPOSE 9000

ENTRYPOINT ["python", "-m", "app.scheduler"]
