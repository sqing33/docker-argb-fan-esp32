FROM ghcr.io/sqing33/python3.13:alpine

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3232

CMD ["python", "argb.py"]
