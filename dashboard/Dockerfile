FROM python:3.12-slim

WORKDIR /app

COPY dashboard/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard/ ./dashboard/

ENV ALARM_DB_BACKEND=postgresql
ENV ALARM_DATABASE=SystemHealth_EU
ENV ALARM_DASH_PORT=8051

WORKDIR /app/dashboard
EXPOSE 8051

CMD ["python", "app.py"]