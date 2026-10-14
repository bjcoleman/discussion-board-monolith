#!/bin/bash

# Exit on error, undefined variable, or failure in a pipeline.
set -euo pipefail

##############################################################################
##############################################################################
# CHANGE REPO_URL BELOW: REPLACE YOUR_GITHUB_USERNAME WITH YOUR GITHUB
# USERNAME. DO NOT CHANGE THE REPOSITORY NAME (discussion-board-monolith).
##############################################################################
##############################################################################
REPO_URL="https://github.com/bjcoleman/discussion-board-monolith.git"

APP_DIR="/home/ec2-user/discussion-board-monolith"
DB_NAME="discussion_board"
DB_USER="discussion_app"

# Install required packages
sudo yum install -y git python3.12 python3.12-pip mariadb105-server

# Start MariaDB and enable it to start on boot
sudo systemctl enable --now mariadb

# Generate a random password containing only hexadecimal characters
DB_PASSWORD="$(python3.12 -c 'import secrets; print(secrets.token_hex(24))')"

# Create the database and application user
mysql <<SQL
CREATE DATABASE IF NOT EXISTS ${DB_NAME};

CREATE USER IF NOT EXISTS '${DB_USER}'@'127.0.0.1'
IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'127.0.0.1'
IDENTIFIED BY '${DB_PASSWORD}';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES
ON ${DB_NAME}.* TO '${DB_USER}'@'127.0.0.1';

FLUSH PRIVILEGES;
SQL

# Clone the repository
git clone "$REPO_URL" "$APP_DIR"
cd "$APP_DIR"

# Install Python dependencies and the project package
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .

# Create a private environment file for the application
cat > .env <<ENV
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=${DB_NAME}
MYSQL_USER=${DB_USER}
MYSQL_PASSWORD=${DB_PASSWORD}
ENV

chown ec2-user:ec2-user .env
chmod 600 .env

# Make sure the application files belong to ec2-user
chown -R ec2-user:ec2-user "$APP_DIR"

# Create the database tables
.venv/bin/python scripts/wait_for_mysql.py --timeout 60
.venv/bin/python scripts/create_table.py


sudo cp deploy/discussion.service /etc/systemd/system/

# Start the application service
sudo systemctl daemon-reload
sudo systemctl enable --now discussion.service
