# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY .env .
COPY user_management_service/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code to the working directory
COPY . .

# Expose the port the app runs on
EXPOSE 8003

# Define the command to run the application
# We use main:app because the uvicorn.run call in main.py uses "main:app"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
