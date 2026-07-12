FROM python:3.11-slim

# Non-root user (security best practice)
RUN groupadd -r healmesh && useradd -r -g healmesh healmesh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER healmesh

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
