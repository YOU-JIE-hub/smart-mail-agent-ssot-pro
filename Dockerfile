FROM python:3.10-slim AS build
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
COPY . /app
RUN python -m pip install -U pip && \
    pip install --no-cache-dir "fastapi>=0.112" "uvicorn[standard]>=0.23" prometheus_client \
    joblib "scikit-learn>=1.3,<2" "numpy<2" "pandas>=2" pyyaml matplotlib safetensors

FROM gcr.io/distroless/python3-debian12
WORKDIR /app
COPY --from=build /usr/share/fonts /usr/share/fonts
COPY --from=build /usr/local/lib/python3.10 /usr/local/lib/python3.10
COPY --from=build /app /app
ENV PORT=8000 PYTHONPATH=/app
USER 65532:65532
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python3","-c","import os,urllib.request,sys; url=f\"http://127.0.0.1:{os.getenv('PORT','8000')}/health\"; sys.exit(0 if urllib.request.urlopen(url, timeout=2).read() else 1)"]
CMD ["-m","uvicorn","service.app:app","--host","0.0.0.0","--port","8000","--access-log"]
