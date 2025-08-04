#!/bin/bash


set -e

echo "🛠 Creating log collectors for LLMedic containers..."

# Directory to store logs
LOG_DIR="/var/log/llmedic"
mkdir -p "$LOG_DIR"
chown $USER:$USER "$LOG_DIR"

# Define services
declare -A services=(
  ["inference_service"]="inference"
  ["download_service"]="download"
  ["finetuning_service"]="finetune"
)

# Loop and create each systemd unit
for container in "${!services[@]}"; do
  name=${services[$container]}
  unit_file="/etc/systemd/system/llmedic-${name}-logs.service"

  echo "⚙️ Creating $unit_file"

  cat <<EOF | sudo tee "$unit_file" > /dev/null
[Unit]
Description=LLMedic ${name^} Service Log Collector
After=docker.service
Requires=docker.service

[Service]
ExecStart=/usr/bin/docker logs -f $container
StandardOutput=append:${LOG_DIR}/${name}.log
StandardError=append:${LOG_DIR}/${name}.log
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

done

# Reload systemd
echo "🔄 Reloading systemd..."
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

# Enable and start all services
for name in "${services[@]}"; do
  echo "🚀 Enabling and starting llmedic-${name}-logs.service"
  sudo systemctl enable llmedic-${name}-logs.service
  sudo systemctl start llmedic-${name}-logs.service
done

echo "✅ All log collectors set up and running."

