#!/bin/bash

if ! dpkg -s postfix &> /dev/null; then
  # Check if postfix and mailutils are installed
  if ! dpkg -s postfix &> /dev/null || ! dpkg -s mailutils &> /dev/null; then
    # Prompt the user to install postfix and mailutils
    read -p "Postfix and/or mailutils are not installed. Do you want to install them now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      # Install postfix & mailutils
      if [ -x "$(command -v yum)" ]; then
        # Use yum to install postfix & mailutils
        sudo yum install postfix mailutils
      elif [ -x "$(command -v dnf)" ]; then
        # Use dnf to install postfix & mailutils
        sudo dnf install postfix mailutils
      else
        # Use apt to install postfix & mailutils
        sudo apt update
        sudo apt install postfix mailutils
      fi
    fi
  fi
  # Start postfix
  sudo systemctl start postfix
fi


# show usage if no arguments are provided
if [ $# -eq 0 ]; then
  echo "Usage: ./mailspoofsent.sh [--bcc bcc_address] --mail-from mail_from --mail-to mail_to --mail-envelope mail_envelope --subject subject --body body"
  exit
fi

# parse arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -h|--help)
      echo "Usage: ./mailspoofsent.sh [--bcc bcc_address] --mail-from mail_from --mail-to mail_to --mail-envelope mail_envelope --subject subject --body body"
      echo ""
      echo "Options:"
      echo "  --bcc bcc_address   Specify a bcc address for the email"
      echo "  --mail-from         The sender's email address"
      echo "  --mail-to           The recipient's email address"
      echo "  --mail-envelope     The envelope sender for the email"
      echo "  --subject           The subject of the email"
      echo "  --body              The body of the email"
      exit
      ;;
    --bcc)
      bcc_address="$2"
      shift
      shift
      ;;
    --mail-from)
      mail_from="$2"
      shift
      shift
      ;;
    --mail-to)
      mail_to="$2"
      shift
      shift
      ;;
    --mail-envelope)
      mail_envelope="$2"
      shift
      shift
      ;;
    --subject)
      subject="$2"
      shift
      shift
      ;;
    --body)
      body="$2"
      shift
      shift
      ;;
    *)
      shift
      ;;
  esac
done

# Fake domainname in Postfix configuration
MAIL_FROM_DOMAIN=$(echo $mail_from | awk -F@ '{print $2}')
sed -i "s/^myhostname =.*/myhostname = $MAIL_FROM_DOMAIN/" /etc/postfix/main.cf

# add List-Unsubscribe header
mail_headers="$mail_headers -aList-Unsubscribe:<mailto:unsubscribe@example.com?subject=unsubscribe>"

# get domain from mail_from argument
domain=$(echo $mail_from | awk -F@ '{print $2}')

# replace example.com domain with domain from mail_from argument
mail_headers=$(echo $mail_headers | sed "s/example.com/$domain/")

# send the email using the mail command
if [ -z "$bcc_address" ]; then
  mail -s "$subject" -r "$mail_from" -a "Content-Type: text/html" -a "Envelope-From: $mail_envelope" "$mail_headers" "$mail_to" <<< "$body"
else
  mail -s "$subject" -r "$mail_from" -a "Content-Type: text/html" -a "Envelope-From: $mail_envelope" -b "$bcc_address" "$mail_headers" "$mail_to" <<< "$body"
fi

# check if the mail command was successful
if [ $? -eq 0 ]; then
  echo "Email sent successfully!"
else
  echo "Failed to send email!"
fi
