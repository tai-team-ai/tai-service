FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

COPY . /app
RUN pip install loguru pydantic

WORKDIR /app

RUN pip install fastapi uvicorn

EXPOSE 8080

CMD ["uvicorn", "main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]