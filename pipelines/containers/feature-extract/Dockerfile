FROM python:3.11-slim
RUN apt-get update && apt-get install -y build-essential
WORKDIR /app
COPY ../../../lib /tmp/lib
RUN pip install --no-cache-dir -e /tmp/lib
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY extract_features.py .
ENTRYPOINT ["python", "extract_features.py"]