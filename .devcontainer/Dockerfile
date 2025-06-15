# Start from a standard Python 3.11 image.
FROM python:3.11-slim-bookworm

# Set the working directory in the container to /workspaces/ryobi_gdo
WORKDIR /workspaces/ryobi_gdo

# Copy the requirements files into the container
COPY requirements.txt .
COPY requirements-test.txt .
COPY requirements-dev.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy the rest of the application code into the container
COPY . .