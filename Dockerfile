# Container image for the Legal AI Copilot workbench (Streamlit).
# Works on Fly.io / Render / Railway / any Docker-hosting platform.
# Python 3.14 is required: the source uses PEP 701 nested f-strings
# (e.g. legal_assistant/citation_utils.py) that do not parse on 3.11/3.12.
# The whole app + 97 tests are verified locally on Python 3.14.3, so the
# cloud image must match that exact interpreter version.
FROM python:3.14-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_STATIC_SERVING=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Most platforms inject $PORT; default to 8501 for local docker runs.
EXPOSE 8501

CMD ["sh", "-c", "streamlit run app/streamlit_app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
