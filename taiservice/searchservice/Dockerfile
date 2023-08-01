FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

COPY . /app

WORKDIR /app

RUN pip install fastapi uvicorn

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]