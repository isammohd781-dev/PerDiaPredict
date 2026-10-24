FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Run as an unprivileged user that owns only the app folder (data files are written here).
RUN useradd --create-home --uid 10001 perdia && chown -R perdia:perdia /app
USER perdia
EXPOSE 8501
# Patient portal. Put it behind the HTTPS proxy in deploy/; secrets come from the environment.
CMD ["streamlit", "run", "patient.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
