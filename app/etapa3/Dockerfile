FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 HF_HOME=/datos/modelos FASTEMBED_CACHE_PATH=/datos/modelos
COPY app/etapa3/requirements.txt /tmp/requirements.txt
COPY tests/etapa3/requirements.txt /tmp/test-requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt -r /tmp/test-requirements.txt
WORKDIR /servicio
COPY app /servicio/app
EXPOSE 8093
CMD ["uvicorn", "app.etapa3.server:app", "--host", "0.0.0.0", "--port", "8093", "--no-access-log"]
