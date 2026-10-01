FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV APP_HOST=0.0.0.0

COPY app.py motor.py revisor.py ./
COPY templates/ ./templates/
COPY static/ ./static/
COPY Entrada.txt Expresion.txt ./

EXPOSE 5000

CMD ["python", "app.py", "--no-abrir"]