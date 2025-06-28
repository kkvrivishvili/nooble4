# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY agent_orchestrator_service/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY agent_orchestrator_service /app/agent_orchestrator_service
COPY common /app/common
COPY .env /app/

# Expose the port the app runs on
EXPOSE 8001

# Command to run the application
CMD ["uvicorn", "agent_orchestrator_service.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
