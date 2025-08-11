#!/bin/bash


set -e

echo "🩺 Starting LLMedic Environment Validation"
echo "----------------------------------------------"

# Minimum system requirements
MIN_RAM_GB=64
MIN_DISK_GB=50
MIN_DOCKER_VERSION="20.10"
REQUIRED_OS="Ubuntu"
REQUIRED_OS_VERSION="20.04"

ERRORS=()

# ---- 1. Check OS version
OS_NAME=$(lsb_release -si)
OS_VERSION=$(lsb_release -sr)
echo "🔍 OS Check: $OS_NAME $OS_VERSION"
if [[ "$OS_NAME" != "$REQUIRED_OS" ]]; then
  ERRORS+=("Unsupported OS: Requires $REQUIRED_OS. Found: $OS_NAME.")
elif [[ "$(printf '%s\n' "$REQUIRED_OS_VERSION" "$OS_VERSION" | sort -V | head -n1)" != "$REQUIRED_OS_VERSION" ]]; then
  ERRORS+=("OS version must be $REQUIRED_OS_VERSION or higher. Found: $OS_VERSION.")
fi

# ---- 2. Check RAM
RAM_TOTAL_GB=$(awk '/MemTotal/ {print int($2 / 1024 / 1024)}' /proc/meminfo)
echo "🔍 RAM Check: ${RAM_TOTAL_GB}GB available"
if [ "$RAM_TOTAL_GB" -lt "$MIN_RAM_GB" ]; then
  ERRORS+=("At least ${MIN_RAM_GB}GB RAM required. Found: ${RAM_TOTAL_GB}GB.")
fi

# ---- 3. Check disk space
DISK_AVAILABLE_GB=$(df / | awk 'NR==2 {print int($4 / 1024 / 1024)}')
echo "🔍 Disk Check: ${DISK_AVAILABLE_GB}GB available on root"
if [ "$DISK_AVAILABLE_GB" -lt "$MIN_DISK_GB" ]; then
  ERRORS+=("At least ${MIN_DISK_GB}GB free disk space required. Found: ${DISK_AVAILABLE_GB}GB.")
fi

# ---- 4. Check Docker installation
if ! command -v docker &> /dev/null; then
  ERRORS+=("Docker is not installed.")
else
  DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
  echo "🔍 Docker Version: $DOCKER_VERSION"
  if [[ "$(printf '%s\n' "$MIN_DOCKER_VERSION" "$DOCKER_VERSION" | sort -V | head -n1)" != "$MIN_DOCKER_VERSION" ]]; then
    ERRORS+=("Docker version must be $MIN_DOCKER_VERSION or newer. Found: $DOCKER_VERSION.")
  fi
fi

# ---- 5. Check Python 3
if ! command -v python3 &> /dev/null; then
  ERRORS+=("Python 3 is not installed.")
else
  PYTHON_VERSION=$(python3 --version | awk '{print $2}')
  echo "🔍 Python Version: $PYTHON_VERSION"
fi

# ---- 6. Check for Intel Gaudi HPU
echo "🔍 Checking for Gaudi HPU..."
if lspci | grep -qi gaudi; then
  echo "✅ Gaudi HPU detected."
else
  ERRORS+=("Gaudi HPU not detected. Required for inference/fine-tuning.")
fi

# ---- 7. Check Hugging Face connectivity
echo "🔍 Checking internet access to Hugging Face..."
if curl -s --head https://huggingface.co | grep "200 OK" > /dev/null; then
  echo "✅ Hugging Face is reachable."
else
  ERRORS+=("Cannot access huggingface.co. Check internet or firewall settings.")
fi

# ---- 8. Check model directory access
MODEL_PATH="/shared/models"
echo "🔍 Checking model path: $MODEL_PATH"
if [ -d "$MODEL_PATH" ]; then
  echo "✅ Model directory is accessible."
elif [ -f "$MODEL_PATH" ]; then
  echo "✅ Model file exists at $MODEL_PATH."
else
  ERRORS+=("Model path not found or inaccessible: $MODEL_PATH.")
fi


# ---- Final Summary
echo "----------------------------------------------"
if [ ${#ERRORS[@]} -eq 0 ]; then
  echo "✅ Environment validation passed. Ready for deployment."
else
  echo "❌ Validation failed with the following issues:"
  for err in "${ERRORS[@]}"; do
    echo "  - $err"
  done
  echo "💡 Please resolve these issues before running deployment."
  exit 1
fi

