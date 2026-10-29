FROM python:3.12-slim
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY app/homologacion/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /servicio
COPY app/__init__.py /servicio/app/__init__.py
COPY app/homologacion /servicio/app/homologacion
EXPOSE 8094
CMD ["uvicorn", "app.homologacion.server:app", "--host", "0.0.0.0", "--port", "8094", "--no-access-log"]
