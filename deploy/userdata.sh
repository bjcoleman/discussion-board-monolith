#!/bin/bash
set -euo pipefail

REPO_URL="https://github.com/cs390f26/discussion-board-monolith.git"
APP_DIR="/home/ec2-user/discussion-board-monolith"

# 2. Install required packages
yum install -y python3.12 git

# 3. Clone directly into /home/ec2-user to match the systemd WorkingDirectory
git clone "$REPO_URL" "$APP_DIR"
cd "$APP_DIR"

# 4. Explicitly use python3.12 to create the virtual environment
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .

# 5. Fix ownership (script runs as root, but service runs as ec2-user)
chown -R ec2-user:ec2-user "$APP_DIR"

# 6. Install and start the systemd service
cp deploy/discussion.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now discussion.service