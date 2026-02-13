FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config

ENV TZ=Asia/Shanghai
ENV APP_CONFIG=/config/rules.yaml
ENV MEDIA_ROOT=/media
ENV VIRTUAL_ROOT=/virtual
ENV CRON_EXPR=30 3 * * *
ENV APP_DB=/data/app.db

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
