# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY .env .
COPY ingestion_service/requirements.txt .

# Install any needed packages specified in requirements.txt
# Adding gcc for potential C extensions in dependencies
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r requirements.txt

# Copy the service code into the container, preserving the directory structure
COPY ingestion_service/ /app/ingestion_service/

# Copy the common module
COPY common/ /app/common/

# Set PYTHONPATH to include the root app directory
ENV PYTHONPATH=/app

# Expose the port the app runs on
EXPOSE 8002

# Define the command to run the application
# Using the module path as seen in main.py's uvicorn.run call
CMD ["uvicorn", "ingestion_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
