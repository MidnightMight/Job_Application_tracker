FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create the data directory and store the database there so it can be mounted as a volume
RUN mkdir -p /data
ENV DB_PATH=/data/jobs.db

# Mark this as a server/Docker deployment to enable multi-user and AI features.
ENV DEPLOYMENT_MODE=docker

EXPOSE 5000

CMD ["python", "app.py"]
