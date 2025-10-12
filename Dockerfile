# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project's code into the container
COPY . .

# Make port 5000 available to the world outside this container
# Hugging Face Spaces uses port 7860 by default, but Flask runs on 5000.
# We need to tell the app to run on the correct port and be accessible.
ENV PORT=7860

# Command to run your Flask application
# We use 0.0.0.0 to make it accessible outside the container
CMD ["python", "backend/app.py", "--host", "0.0.0.0", "--port", "7860"]