# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the env file and requirements first
COPY .env ./
COPY agent_execution_service/requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the service-specific code into the container
COPY agent_execution_service/ ./agent_execution_service/

# Copy the shared common module
COPY common/ ./common/

# Set Python path to include the app directory
ENV PYTHONPATH=/app

# Expose the port the app runs on
EXPOSE 8005

# Use python -m to ensure the module is found correctly
CMD ["python", "-m", "uvicorn", "agent_execution_service.main:app", "--host", "0.0.0.0", "--port", "8005", "--reload"]