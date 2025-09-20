FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install -U pip && pip install -r requirements.txt
COPY . .
CMD ["python","scripts/eval_all.py"]
