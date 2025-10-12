# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project's code into the container
COPY . .

# Set environment variables for the application
ENV HF_HOME=/tmp/.cache/huggingface/
ENV PORT=7860

# Command to run your Flask application
CMD ["python", "backend/app.py"]