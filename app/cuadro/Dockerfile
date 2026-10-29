FROM python:3.12-slim
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY app/cuadro/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /servicio
COPY app/__init__.py /servicio/app/__init__.py
COPY app/cuadro /servicio/app/cuadro
EXPOSE 8095
CMD ["uvicorn", "app.cuadro.server:app", "--host", "0.0.0.0", "--port", "8095", "--no-access-log"]
