FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENV TRACEFINITY_ONNX_GPU_MEM_LIMIT_MB=10240
ENV TRACEFINITY_ONNX_ARENA_EXTEND_STRATEGY=kSameAsRequested

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
