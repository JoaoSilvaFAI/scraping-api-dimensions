FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY . .

# Install dependencies
RUN uv pip install --system fastapi uvicorn playwright python-dotenv

# Install chromium specifically
RUN playwright install chromium

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
