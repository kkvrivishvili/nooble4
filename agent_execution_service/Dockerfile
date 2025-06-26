# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file from its service-specific directory
COPY .env .
COPY agent_execution_service/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the service-specific code into the container, preserving the directory structure
COPY agent_execution_service/ /app/agent_execution_service/

# Copy the shared common module
COPY common/ /app/common/

# Add the app directory to the Python path to ensure modules are found
ENV PYTHONPATH=/app

# Expose the port the app runs on
EXPOSE 8005

# Define the command to run the application
# We use 0.0.0.0 to ensure it's accessible from outside the container
CMD ["uvicorn", "agent_execution_service.main:app", "--host", "0.0.0.0", "--port", "8005"]
