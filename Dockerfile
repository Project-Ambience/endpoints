# Dockerfile for Habana Gaudi

# IMPORTANT: Choose the correct Habana Labs base image.
# Check Habana's official documentation (e.g., for SynapseAI, Gaudi Docker images)
# The tag will depend on your SynapseAI version, PyTorch/TF version, and OS.
# Example for PyTorch:
FROM vault.habana.ai/gaudi-ai-public/pytorch:2.2.0-ubuntu22.04 # <--- REPLACE WITH YOUR SPECIFIC GAUDI/SYNAPSEAI IMAGE

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if any are needed (e.g., git-lfs for large models)
# These base images are usually quite complete, but sometimes git-lfs or other
# developer tools might be useful for your specific workflow.
RUN apt-get update && apt-get install -y \
    git-lfs \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python packages specified in requirements.txt
# PyTorch will be "satisfied" by the base image's installation.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy your application code into the container
COPY download_model.py .

# Expose port 8000 for the FastAPI application
EXPOSE 8000

# Command to run the application using Uvicorn
CMD ["uvicorn", "download_model:app", "--host", "0.0.0.0", "--port", "8000"]

