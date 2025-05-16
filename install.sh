#!/bin/bash

# Check if the script is being run with sudo rights
if [ "$(id -u)" != "0" ]; then
  # Show disclaimer and exit
  echo "DISCLAIMER: This script requires sudo rights to run."
  exit 1
fi

# Install postfix and mailutils
echo "Installing postfix and mailutils..."
if [ -x "$(command -v yum)" ]; then
  # Use yum to install postfix & mailutils
  yum install -y postfix mailutils
elif [ -x "$(command -v dnf)" ]; then
  # Use dnf to install postfix & mailutils
  dnf install -y postfix mailutils
elif [ -x "$(command -v apt-get)" ]; then
  # Use apt-get to install postfix & mailutils
  apt-get update
  apt-get install -y postfix mailutils
else
  echo "Error: Package manager not found. Please install postfix and mailutils manually."
  exit 1
fi

# Install Python
echo "Installing Python..."
if [ -x "$(command -v yum)" ]; then
  # Use yum to install Python
  yum install -y python3
elif [ -x "$(command -v dnf)" ]; then
  # Use dnf to install Python
  dnf install -y python3
elif [ -x "$(command -v apt-get)" ]; then
  # Use apt-get to install Python
  apt-get install -y python3
else
  echo "Error: Package manager not found. Please install Python manually."
  exit 1
fi

# Install pip
echo "Installing pip..."
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py

# Install Flask
echo "Installing Flask..."
pip install flask

echo "Installation completed successfully."
echo "You can now run the 'mailspoofsent.sh' script to send spoofed emails."
