#!/usr/bin/env python3
import os
import time
import random
import subprocess
import shlex
import json
from datetime import datetime
import threading
import sys
import pwd
import tempfile
import re
import smtplib
import socket
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
import uuid
import base64
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from scripts.encryption import encrypt_password, decrypt_password

# Add scripts directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(current_dir, 'scripts')
sys.path.insert(0, scripts_dir)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
app.config['LOG_FILE'] = '/tmp/log.json'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DRAFTS_FOLDER'] = 'drafts'
app.config['CAMPAIGNS_FOLDER'] = 'campaigns'
app.config['TEMPLATES_FOLDER'] = 'templates_catalog'  # New folder for email templates
app.config['MAILBOXES_FILE'] = 'mailboxes.json' # New file for mailboxes

# Create required directories if they don't exist
for folder in [app.config['UPLOAD_FOLDER'], app.config['DRAFTS_FOLDER'], 
               app.config['CAMPAIGNS_FOLDER'], app.config['TEMPLATES_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Check if running with sudo/root privileges
def is_root():
    return os.geteuid() == 0

# Import and register domain checker routes AFTER app is created
try:
    from domain_checker import domain_checker, register_routes
    register_routes(app)
    print("Domain checker routes registered successfully!")
except ImportError as e:
    print(f"Warning: Could not import domain_checker module: {e}")
    print("DNS check functionality will be disabled.")

# Function to check if a package is installed
def is_package_installed(package_name):
    try:
        result = subprocess.run(['dpkg', '-s', package_name], 
                                capture_output=True, 
                                text=True)
        return result.returncode == 0
    except:
        try:
            # Try using which for more general compatibility
            result = subprocess.run(['which', package_name], 
                                    capture_output=True, 
                                    text=True)
            return result.returncode == 0
        except:
            return False

# Function to install packages
def install_packages(packages):
    # Determine package manager
    package_managers = {
        'apt': 'apt update && apt install -y',
        'yum': 'yum install -y',
        'dnf': 'dnf install -y'
    }
    
    package_manager = None
    for pm, _ in package_managers.items():
        try:
            if subprocess.run(['which', pm], capture_output=True).returncode == 0:
                package_manager = pm
                break
        except:
            continue
    
    if not package_manager:
        return False, "No supported package manager found"
    
    try:
        cmd = f"{package_managers[package_manager]} {' '.join(packages)}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

# Add or update a setting in Postfix configuration
def update_postfix_setting(setting, value):
    try:
        with open('/etc/postfix/main.cf', 'r') as f:
            config_lines = f.readlines()
            
        # Check if setting exists
        setting_exists = False
        for i, line in enumerate(config_lines):
            if line.strip().startswith(f"{setting} ="):
                config_lines[i] = f"{setting} = {value}\n"
                setting_exists = True
                break
                
        # If it doesn't exist, add it
        if not setting_exists:
            config_lines.append(f"{setting} = {value}\n")
            
        # Write the configuration back
        with open('/etc/postfix/main.cf', 'w') as f:
            f.writelines(config_lines)
            
        return True
    except Exception as e:
        print(f"Error updating postfix setting {setting}: {str(e)}")
        return False


# Configure postfix for email spoofing - following the shell script approach
def configure_postfix(spoof_domain, mail_envelope, mail_from):
    try:
        print("[+] Updating hostname to match spoof domain for PTR record lookup...")
        update_postfix_setting('myhostname', spoof_domain)
        
        print("[+] Updating mydestination to include the hostname...")
        update_postfix_setting('mydestination', '$myhostname, localhost.localdomain, , localhost')
        
        print("[+] Setting smtp.mailfrom to bypass SPF...")
        update_postfix_setting('smtp.mailfrom', mail_envelope)
        
        print("[+] Setting header.from to control From header...")
        update_postfix_setting('header.from', mail_from)
        
        print("[+] Restarting postfix to apply changes...")
        subprocess.run(['systemctl', 'restart', 'postfix'], check=True)
        
        return True, "Postfix configuration updated successfully"
    except Exception as e:
        return False, f"Error configuring postfix: {str(e)}"

# Clean up postfix configuration - exactly like the shell script
def cleanup_postfix():
    try:
        print("[-] Cleaning up for next run...")
        
        # Read existing config
        with open('/etc/postfix/main.cf', 'r') as f:
            config_lines = f.readlines()
        
        # Remove smtp.mailfrom and header.from lines
        filtered_lines = [line for line in config_lines 
                          if not line.strip().startswith('smtp.mailfrom =') 
                          and not line.strip().startswith('header.from =')]
        
        # Write back the filtered config
        with open('/etc/postfix/main.cf', 'w') as f:
            f.writelines(filtered_lines)
        
        print("[+] Restarting postfix after cleanup...")
        subprocess.run(['systemctl', 'restart', 'postfix'], check=True)
        
        return True, "Postfix configuration cleaned up successfully"
    except Exception as e:
        return False, f"Error cleaning up postfix configuration: {str(e)}"

# Function to send email - following the shell script approach closely
def send_spoofed_email(mail_from, mail_to, mail_envelope, subject, body, spoof_domain, bcc=None, html_body_path=None, attachments=None):
    if not is_root():
        return False, "This function requires root privileges to run"
    
    # Check if postfix is installed
    if not is_package_installed('postfix') or not is_package_installed('mailutils'):
        print("Postfix and/or mailutils are not installed.")
        return False, "Postfix and/or mailutils are not installed"
    
    # Check postfix status and start if needed
    try:
        status = subprocess.run(['systemctl', 'status', 'postfix'], 
                               capture_output=True, 
                               text=True)
        
        if 'active' not in status.stdout:
            subprocess.run(['systemctl', 'start', 'postfix'], check=True)
            print("[+] Postfix has been started...")
        else:
            print("[-] Postfix is already started, ready to start...")
    except Exception as e:
        return False, f"Error checking/starting postfix: {str(e)}"
    
    # Configure postfix for spoofing
    success, message = configure_postfix(spoof_domain, mail_envelope, mail_from)
    if not success:
        return False, message
    
    # Prepare the body
    if html_body_path and os.path.exists(html_body_path):
        with open(html_body_path, 'r') as f:
            email_body = f.read()
    else:
        # Wrap plain text in HTML if not already HTML
        if not body.strip().startswith('<html'):
            email_body = f"<html>{body}</html>"
        else:
            email_body = body
    
    # Extract domain from mail_from for the unsubscribe header
    try:
        mail_from_domain = mail_from.split('@')[1]
    except IndexError:
        mail_from_domain = 'example.com'
    
    try:
        # Exactly match the mail command from the shell script
        mail_cmd = [
            'mail',
            '-s', subject,
            '-a', f'From: {mail_from}',
            '-a', 'Content-Type: text/html;',
            '-a', f'Return-Path: {mail_envelope}',
            '-a', f'List-Unsubscribe:<mailto:unsubscribe@{mail_from_domain}?subject=unsubscribe>'
        ]
        
        # Add BCC if specified
        if bcc:
            mail_cmd.extend(['-a', f'BCC: {bcc}'])
        
        # Add attachments if specified
        if attachments:
            for attachment in attachments:
                mail_cmd.extend([f'--attach={attachment}'])

        # Add destination email
        mail_cmd.append(mail_to)
        
        # Print the mail command for debugging
        print(f"Executing mail command: {' '.join(mail_cmd)}")
        
        # Execute mail command
        process = subprocess.Popen(mail_cmd, stdin=subprocess.PIPE, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True)
        
        stdout, stderr = process.communicate(input=email_body)
        
        # Clean up postfix config
        cleanup_result, cleanup_message = cleanup_postfix()
        if not cleanup_result:
            print(f"Warning: {cleanup_message}")
        
        if process.returncode == 0:
            return True, "Email sent successfully"
        else:
            return False, f"Failed to send email: {stderr}"
            
    except Exception as e:
        # Make sure to clean up even if there's an error
        cleanup_postfix()
        return False, f"Error sending email: {str(e)}"



# New function to send authenticated email
def send_authenticated_email(sender_email, sender_password, smtp_server, smtp_port, use_tls, recipient_email, subject, body, html_body_path=None, base_path_for_images=None, attachments=None):
    try:
        decrypted_password = decrypt_password(sender_password)

        html_content = None
        if html_body_path and os.path.exists(html_body_path):
            with open(html_body_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            if base_path_for_images is None:
                base_path_for_images = os.path.dirname(html_body_path)
        elif body.strip().startswith('<html') or re.search(r'<[a-z][\s\S]*>', body):
            html_content = body
            if base_path_for_images is None:
                base_path_for_images = app.config['UPLOAD_FOLDER']

        images_to_embed = []
        if html_content:
            # Find all images to embed, including data URIs
            for img_match in re.finditer(r"""<img[^>]+src=['"]([^'"]+)['"]""", html_content):
                img_src = img_match.group(1)
                cid = f'{uuid.uuid4()}@mailspoofsent'
                
                if img_src.startswith('data:image'):
                    try:
                        # Handle data URI
                        header, encoded_data = img_src.split(',', 1)
                        img_type = header.split(';')[0].split('/')[1]
                        img_data = base64.b64decode(encoded_data)
                        
                        image = MIMEImage(img_data, _subtype=img_type)
                        image.add_header('Content-ID', f'<{cid}>')
                        image.add_header('Content-Disposition', 'inline')
                        images_to_embed.append({'src': img_src, 'cid': cid, 'mime_image': image})
                    except Exception as e:
                        print(f"Error processing data URI image: {e}")

                elif not img_src.startswith(('http://', 'https://')):
                    # Handle local file path
                    img_path = os.path.join(base_path_for_images, img_src)
                    if os.path.exists(img_path):
                        try:
                            with open(img_path, 'rb') as img_file:
                                img_data = img_file.read()
                            
                            img_type = os.path.splitext(img_path)[1].lower().strip('.')
                            if img_type in ['png', 'jpeg', 'jpg', 'gif']:
                                image = MIMEImage(img_data, _subtype=img_type)
                                image.add_header('Content-ID', f'<{cid}>')
                                image.add_header('Content-Disposition', 'inline', filename=os.path.basename(img_path))
                                images_to_embed.append({'src': img_src, 'cid': cid, 'mime_image': image})
                            else:
                                print(f"Warning: Unsupported image type for {img_path}. Skipping embedding.")
                        except Exception as e:
                            print(f"Error preparing image for embedding {img_path}: {e}")
                    else:
                        print(f"Warning: Image file not found: {img_path}. Skipping embedding.")

        if images_to_embed:
            # If there are images, the main container is 'related'
            msg = MIMEMultipart('related')
            msg["From"] = sender_email
            msg["To"] = recipient_email
            msg["Subject"] = subject

            # The first part of a 'related' message should be the 'alternative' part
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)

            # Attach plain text part
            text_part = MIMEText(body, "plain", _charset='UTF-8')
            msg_alternative.attach(text_part)

            # Replace image sources with CIDs in HTML
            for img_info in images_to_embed:
                html_content = html_content.replace(img_info['src'], f"cid:{img_info['cid']}")

            # Attach HTML part
            html_part = MIMEText(html_content, "html", _charset='UTF-8')
            msg_alternative.attach(html_part)

            # Attach images to the main 'related' message
            for img_info in images_to_embed:
                msg.attach(img_info['mime_image'])
        else:
            # If no images, the main container is 'alternative'
            msg = MIMEMultipart('alternative')
            msg["From"] = sender_email
            msg["To"] = recipient_email
            msg["Subject"] = subject

            # Attach plain text part
            text_part = MIMEText(body, "plain", _charset='UTF-8')
            msg.attach(text_part)

            # Attach HTML part if it exists
            if html_content:
                html_part = MIMEText(html_content, "html", _charset='UTF-8')
                msg.attach(html_part)

        # Add attachments
        if attachments:
            for attachment_path in attachments:
                try:
                    with open(attachment_path, "rb") as attachment_file:
                        part = MIMEApplication(attachment_file.read(), Name=os.path.basename(attachment_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                    msg.attach(part)
                except Exception as e:
                    print(f"Error attaching file {attachment_path}: {e}")

        server = None
        try:
            if smtp_port == 465:
                # For SMTPS (implicit SSL/TLS on port 465)
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10, context=ssl.create_default_context())
            elif use_tls:
                # For STARTTLS (explicit TLS on other ports like 587)
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                server.starttls(context=ssl.create_default_context())
            else:
                # Plain SMTP without encryption
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            
            server.set_debuglevel(1)  # Enable debug output for the connection
        except socket.timeout:
            return False, f"Connection timed out to {smtp_server}:{smtp_port}. Check server address and port, or network connectivity."
        except ConnectionRefusedError:
            return False, f"Connection refused by {smtp_server}:{smtp_port}. Ensure the SMTP server is running and accessible."
        except ssl.SSLError as e:
            return False, f"SSL/TLS Error: {str(e)}. This might indicate an issue with certificates or an incorrect SSL/TLS setting."
        except smtplib.SMTPConnectError as e:
            return False, f"SMTP Connection Error: {e.smtp_code} - {e.smtp_error.decode()}"
        except Exception as e:
            return False, f"Error establishing SMTP connection: {str(e)}"
        
        server.login(sender_email, decrypted_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        
        return True, "Email sent successfully via authenticated SMTP"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentication Error: {e.smtp_code} - {e.smtp_error.decode()}"
    except smtplib.SMTPException as e:
        return False, f"SMTP Error: {str(e)}"
    except Exception as e:
        import traceback
        traceback.print_exc() # Print full traceback for unexpected errors
        return False, f"An unexpected error occurred: {str(e)}"

# Check sudo requirement
@app.before_request
def check_sudo():
    if not is_root() and request.path != '/sudo-required' and not request.path.startswith('/static/'):
        return redirect(url_for('sudo_required'))

@app.route('/sudo-required')
def sudo_required():
    """Show message that sudo is required"""
    return render_template('sudo_required.html')

# Template filters
@app.template_filter('format_timestamp')
def format_timestamp(timestamp):
    """Format timestamp from draft_id or campaign_id"""
    try:
        # Convert milliseconds to datetime
        dt = datetime.fromtimestamp(int(timestamp) / 1000)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return 'Unknown Date'

# Routes
@app.route('/')
def home():
    """Main page to send individual emails"""
    log_data = load_log_data()
    
    # Get templates for dropdown
    templates = get_all_templates()
    
    # Get drafts for dropdown
    drafts = []
    for f in os.listdir(app.config['DRAFTS_FOLDER']):
        if f.endswith('.json'):
            draft_id = f.replace('.json', '')
            try:
                with open(os.path.join(app.config['DRAFTS_FOLDER'], f), 'r') as draft_file:
                    draft_content = json.load(draft_file)
                    draft_name = draft_content.get('name', f'Draft {datetime.fromtimestamp(int(draft_id.split("_")[1]) / 1000).strftime('%Y-%m-%d %H:%M:%S')}')
                    # If there's an HTML body path, read the content
                    if draft_content.get('html_body_path') and os.path.exists(draft_content['html_body_path']):
                        with open(draft_content['html_body_path'], 'r') as draft_html_file:
                            draft_content['html_body_content'] = draft_html_file.read()
                    drafts.append({'id': draft_id, 'name': draft_name, 'content': draft_content})
            except Exception as e:
                print(f"Error loading draft {draft_id}: {e}")
                drafts.append({'id': draft_id, 'name': f'Draft {draft_id}'})
    drafts = sorted(drafts, key=lambda x: x['name'].lower())
    
    # Get mailboxes for dropdown
    mailboxes = load_mailboxes()

    # Current timestamp for draft ID
    current_time = time.time()
    now_timestamp = int(current_time * 1000)
    
    return render_template('index.html', log_data=log_data, templates=templates, 
                          drafts=drafts, current_time=current_time, now_timestamp=now_timestamp,
                          mailboxes=mailboxes)

@app.route('/send-email', methods=['POST'])
def send_email():
    """Process the email sending form"""
    mail_from = request.form['mail_from']
    mail_to = request.form['mail_to']
    mail_envelope = request.form['mail_envelope']
    subject = request.form['subject']
    body = request.form.get('body', '')
    spoof_domain = request.form['spoof_domain']
    bcc = request.form.get('bcc', '')
    mailbox_id = request.form.get('mailbox_id') # New: Get mailbox ID
    
    # Handle HTML body file upload
    html_file = request.files.get('html_body')
    html_body_path = ''
    if html_file and html_file.filename:
        html_body_path = os.path.join(app.config['UPLOAD_FOLDER'], html_file.filename)
        html_file.save(html_body_path)
        base_path_for_images = app.config['UPLOAD_FOLDER']
    elif body.strip().startswith('<html') or re.search(r'<[a-z][\s\S]*>', body):
        base_path_for_images = app.config['UPLOAD_FOLDER']
    else:
        base_path_for_images = None

    # Handle attachments
    attachments = []
    if 'attachments' in request.files:
        for attachment_file in request.files.getlist('attachments'):
            if attachment_file and attachment_file.filename:
                attachment_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment_file.filename)
                attachment_file.save(attachment_path)
                attachments.append(attachment_path)
    
    success = False
    message = ""

    if mailbox_id and mailbox_id != "none": # If a mailbox is selected
        mailboxes = load_mailboxes()
        mailbox = next((mb for mb in mailboxes if mb['id'] == mailbox_id), None)
        if mailbox:
            success, message = send_authenticated_email(
                sender_email=mailbox['username'],
                sender_password=decrypt_password(mailbox['password']),\
                smtp_server=mailbox['smtp_server'],
                smtp_port=mailbox['smtp_port'],
                use_tls=mailbox['use_tls'],
                recipient_email=mail_to,
                subject=subject,
                body=body,
                html_body_path=html_body_path if html_body_path else None,
                base_path_for_images=base_path_for_images,
                attachments=attachments
            )
        else:
            success = False
            message = "Selected mailbox not found."
    else: # Use spoofing method
        # Send the email
        success, message = send_spoofed_email(
            mail_from=mail_from,
            mail_to=mail_to,
            mail_envelope=mail_envelope,
            subject=subject,
            body=body,
            spoof_domain=spoof_domain,
            bcc=bcc if bcc else None,
            html_body_path=html_body_path if html_body_path else None,
            attachments=attachments
        )
    
    # Log the email sending
    log_entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'email': f'From: {mail_from}, To: {mail_to}, Subject: {subject}',
        'success': success,
        'message': message
    }
    
    # Add to log file
    log_data = load_log_data()
    log_data.append(log_entry)
    with open(app.config['LOG_FILE'], 'w') as f:
        json.dump(log_data, f, indent=4)
    
    # Emit socket event
    socketio.emit('log_update', log_entry)
    
    return redirect(url_for('home'))

@app.route('/log', methods=['GET'])
def log():
    """Return log data as JSON"""
    log_data = load_log_data()
    return jsonify({'log': log_data})

# Template Management Routes
@app.route('/templates', methods=['GET'])
def manage_templates():
    """Template management page"""
    templates = get_all_templates()
    return render_template('templates.html', templates=templates)

@app.route('/templates/add', methods=['POST'])
def add_template():
    """Add a new template"""
    template_data = {
        'name': request.form['template_name'],
        'description': request.form.get('template_description', ''),
        'subject': request.form.get('subject', ''),
        'body': request.form.get('body', ''),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Generate template ID based on timestamp
    template_id = f"template_{int(time.time() * 1000)}"
    
    # Save template to file
    template_path = os.path.join(app.config['TEMPLATES_FOLDER'], f'{template_id}.json')
    with open(template_path, 'w') as f:
        json.dump(template_data, f, indent=4)
    
    # Handle HTML file upload if provided
    html_file = request.files.get('html_body')
    if html_file and html_file.filename:
        html_path = os.path.join(app.config['TEMPLATES_FOLDER'], f'{template_id}.html')
        html_file.save(html_path)
    
    return jsonify({'success': True, 'template_id': template_id})

@app.route('/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    """Get template details"""
    template_path = os.path.join(app.config['TEMPLATES_FOLDER'], f'{template_id}.json')
    html_path = os.path.join(app.config['TEMPLATES_FOLDER'], f'{template_id}.html')
    
    if not os.path.exists(template_path):
        return jsonify({'error': 'Template not found'}), 404
    
    with open(template_path, 'r') as f:
        template_data = json.load(f)
    
    # Check if HTML file exists
    if os.path.exists(html_path):
        with open(html_path, 'r') as f:
            template_data['html_body'] = f.read()
    
    return jsonify(template_data)

@app.route('/templates/<template_id>/delete', methods=['POST'])
def delete_template(template_id):
    """Delete a template"""
    template_path = os.path.join(app.config['TEMPLATES_FOLDER'], f'{template_id}.json')
    html_path = os.path.join(app.config['TEMPLATES_FOLDER'], f'{template_id}.html')
    
    try:
        if os.path.exists(template_path):
            os.remove(template_path)
        
        if os.path.exists(html_path):
            os.remove(html_path)
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/templates/<template_id>/edit', methods=['POST'])
def edit_template(template_id):
    """Edit an existing template"""
    template_path = os.path.join(app.config['TEMPLATES_FOLDER'], f'{template_id}.json')
    
    if not os.path.exists(template_path):
        return jsonify({'error': 'Template not found'}), 404
    
    # Load existing template
    with open(template_path, 'r') as f:
        template_data = json.load(f)
    
    # Update with new data
    template_data['name'] = request.form['template_name']
    template_data['description'] = request.form.get('template_description', '')
    template_data['subject'] = request.form.get('subject', '')
    template_data['body'] = request.form.get('body', '')
    template_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Save updated template
    with open(template_path, 'w') as f:
        json.dump(template_data, f, indent=4)
    
    # Handle HTML file upload if provided
    html_file = request.files.get('html_body')
    if html_file and html_file.filename:
        html_path = os.path.join(app.config['TEMPLATES_FOLDER'], f'{template_id}.html')
        html_file.save(html_path)
    
    return jsonify({'success': True})

@app.route('/drafts', methods=['GET', 'POST'])
def manage_drafts():
    """Handle draft operations"""
    if request.method == 'POST':
        draft_data = {
            'mail_from': request.form['mail_from'],
            'mail_to': request.form['mail_to'],
            'mail_envelope': request.form['mail_envelope'],
            'subject': request.form['subject'],
            'body': request.form.get('body', ''),
            'spoof_domain': request.form['spoof_domain'],
            'bcc': request.form.get('bcc', ''),
            'name': request.form.get('draft_name', f'Draft {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}'), # New: Add draft name
            'mailbox_id': request.form.get('mailbox_id', 'none'), # New: Add mailbox ID
            'html_body_path': html_body_path if html_body_path else None # New: Add html_body_path
        }
        
        draft_id = request.form['draft_id']
        with open(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'), 'w') as f:
            json.dump(draft_data, f, indent=4)
        
        # Handle HTML body file upload for drafts
        html_file = request.files.get('html_body')
        if html_file and html_file.filename:
            draft_html_path = os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.html')
            html_file.save(draft_html_path)
            draft_data['html_body_path'] = draft_html_path # Update path in draft_data
            with open(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'), 'w') as f:
                json.dump(draft_data, f, indent=4)

        # If Ajax request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'draft_id': draft_id, 'draft_name': draft_data['name']})
        
    # List all drafts
    drafts = [f for f in os.listdir(app.config['DRAFTS_FOLDER']) if f.endswith('.json')]
    return render_template('drafts.html', drafts=drafts)

@app.route('/draft/<draft_id>', methods=['GET'])
def get_draft(draft_id):
    """API to get draft details"""
    try:
        with open(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'), 'r') as f:
            draft_data = json.load(f)
        
        # If there's an HTML body path, read the content
        if draft_data.get('html_body_path') and os.path.exists(draft_data['html_body_path']):
            with open(draft_data['html_body_path'], 'r') as f:
                draft_data['html_body_content'] = f.read()

        return jsonify(draft_data)
    except FileNotFoundError:
        return jsonify({'error': 'Draft not found'}), 404

@app.route('/draft/<draft_id>/delete', methods=['POST'])
def delete_draft(draft_id):
    """API to delete a draft"""
    try:
        os.remove(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'))
        return jsonify({'success': True})
    except FileNotFoundError:
        return jsonify({'error': 'Draft not found'}), 404

@app.route('/campaigns', methods=['GET', 'POST'])
def manage_campaigns():
    """Handle campaign operations"""
    if request.method == 'POST':
        campaign_data = {
            'name': request.form['campaign_name'],
            'draft_ids': request.form.getlist('draft_ids'),
            'delay_emails': 'delay_emails' in request.form,
            'track_opens': 'track_opens' in request.form,
            'track_clicks': 'track_clicks' in request.form
        }
        
        campaign_id = request.form['campaign_id']
        with open(os.path.join(app.config['CAMPAIGNS_FOLDER'], f'{campaign_id}.json'), 'w') as f:
            json.dump(campaign_data, f, indent=4)
        
        # If Ajax request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'campaign_id': campaign_id})
    
    # Load campaign data
    campaigns = [f for f in os.listdir(app.config['CAMPAIGNS_FOLDER']) if f.endswith('.json')]
    campaign_data = {}
    for campaign in campaigns:
        try:
            with open(os.path.join(app.config['CAMPAIGNS_FOLDER'], campaign), 'r') as f:
                campaign_data[campaign] = json.load(f)
        except:
            pass
    
    drafts = [f for f in os.listdir(app.config['DRAFTS_FOLDER']) if f.endswith('.json')]
    now_timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
    
    return render_template('campaigns.html', campaigns=campaigns, drafts=drafts, 
                           campaign_data=campaign_data, now_timestamp=now_timestamp)

@app.route('/campaign/<campaign_id>', methods=['GET'])
def get_campaign(campaign_id):
    """API to get campaign details"""
    try:
        with open(os.path.join(app.config['CAMPAIGNS_FOLDER'], f'{campaign_id}.json'), 'r') as f:
            campaign_data = json.load(f)
        
        # Load draft details for this campaign
        campaign_data['drafts'] = []
        for draft_id in campaign_data['draft_ids']:
            try:
                with open(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'), 'r') as f:
                    campaign_data['drafts'].append(json.load(f))
            except FileNotFoundError:
                campaign_data['drafts'].append({'error': 'Draft not found'})
        
        return jsonify(campaign_data)
    except FileNotFoundError:
        return jsonify({'error': 'Campaign not found'}), 404

@app.route('/campaign/<campaign_id>/delete', methods=['POST'])
def delete_campaign(campaign_id):
    """API to delete a campaign"""
    try:
        os.remove(os.path.join(app.config['CAMPAIGNS_FOLDER'], f'{campaign_id}.json'))
        return jsonify({'success': True})
    except FileNotFoundError:
        return jsonify({'error': 'Campaign not found'}), 404

@app.route('/campaign/<campaign_id>/launch', methods=['POST'])
def launch_campaign(campaign_id):
    """API to launch a campaign"""
    try:
        with open(os.path.join(app.config['CAMPAIGNS_FOLDER'], f'{campaign_id}.json'), 'r') as f:
            campaign_data = json.load(f)
        
        # Start campaign in background thread
        threading.Thread(target=execute_campaign, args=(campaign_id, campaign_data)).start()
        
        return jsonify({'success': True, 'count': len(campaign_data['draft_ids'])})
    except FileNotFoundError:
        return jsonify({'error': 'Campaign not found'}), 404

@app.route('/install-dependencies', methods=['POST'])
def install_dependencies():
    """Install required system dependencies"""
    if not is_root():
        return jsonify({'success': False, 'message': 'This action requires root privileges'})
    
    success, message = install_packages(['postfix', 'mailutils'])
    return jsonify({'success': success, 'message': message})

@app.route('/static/<path:filename>')
def custom_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

# Mailbox Management Routes
@app.route('/mailboxes', methods=['GET'])
def manage_mailboxes():
    """Mailbox management page"""
    mailboxes = load_mailboxes()
    return render_template('mailboxes.html', mailboxes=mailboxes)

@app.route('/mailboxes/add', methods=['POST'])
def add_mailbox():
    """Add a new mailbox"""
    mailboxes = load_mailboxes()
    mailbox_data = {
        'id': f"mailbox_{int(time.time() * 1000)}",
        'name': request.form['name'],
        'username': request.form['username'],
        'password': encrypt_password(request.form['password']),
        'smtp_server': request.form['smtp_server'],
        'smtp_port': int(request.form['smtp_port']),
        'use_tls': 'use_tls' in request.form,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    mailboxes.append(mailbox_data)
    save_mailboxes(mailboxes)
    return jsonify({'success': True, 'mailbox': mailbox_data})

@app.route('/mailboxes/delete/<mailbox_id>', methods=['POST'])
def delete_mailbox(mailbox_id):
    """Delete a mailbox"""
    mailboxes = load_mailboxes()
    initial_len = len(mailboxes)
    mailboxes = [mb for mb in mailboxes if mb['id'] != mailbox_id]
    if len(mailboxes) < initial_len:
        save_mailboxes(mailboxes)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Mailbox not found'}), 404

@app.route('/mailboxes/test', methods=['POST'])
def test_mailbox():
    """Send a test email using a configured mailbox"""
    mailbox_id = request.form['mailbox_id']
    test_recipient = request.form['test_recipient']
    
    mailboxes = load_mailboxes()
    mailbox = next((mb for mb in mailboxes if mb['id'] == mailbox_id), None)
    
    if not mailbox:
        return jsonify({'success': False, 'message': 'Mailbox not found'}), 404
    
    subject = "MailSpoofSent Test Email"
    body = f"This is a test email sent from MailSpoofSent using mailbox: {mailbox['name']} ({mailbox['username']})."
    
    success, message = send_authenticated_email(
        sender_email=mailbox['username'],
        sender_password=decrypt_password(mailbox['password']),
        smtp_server=mailbox['smtp_server'],
        smtp_port=mailbox['smtp_port'],
        use_tls=mailbox['use_tls'],
        recipient_email=test_recipient,
        subject=subject,
        body=body
    )
    
    return jsonify({'success': success, 'message': message})

# Helper functions
def load_log_data():
    """Load log data from file"""
    if os.path.exists(app.config['LOG_FILE']):
        try:
            with open(app.config['LOG_FILE'], 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def get_all_templates():
    """Get all templates from the templates folder"""
    templates = []
    template_files = [f for f in os.listdir(app.config['TEMPLATES_FOLDER']) if f.endswith('.json')]
    
    for template_file in template_files:
        template_id = template_file.replace('.json', '')
        try:
            with open(os.path.join(app.config['TEMPLATES_FOLDER'], template_file), 'r') as f:
                template_data = json.load(f)
                template_data['id'] = template_id
                templates.append(template_data)
        except:
            continue
    
    # Sort templates by name
    return sorted(templates, key=lambda x: x['name'].lower())

def load_mailboxes():
    """Load mailboxes from file"""
    if os.path.exists(app.config['MAILBOXES_FILE']):
        try:
            with open(app.config['MAILBOXES_FILE'], 'r') as f:
                mailboxes = json.load(f)
                for mailbox in mailboxes:
                    if not mailbox.get('encrypted', False):
                        mailbox['password'] = encrypt_password(mailbox['password'])
                        mailbox['encrypted'] = True
                save_mailboxes(mailboxes)
                return mailboxes
        except json.JSONDecodeError:
            return []
    return []

def save_mailboxes(mailboxes):
    """Save mailboxes to file"""
    with open(app.config['MAILBOXES_FILE'], 'w') as f:
        json.dump(mailboxes, f, indent=4)

def execute_campaign(campaign_id, campaign_data):
    """Execute all emails in a campaign"""
    for draft_id in campaign_data['draft_ids']:
        try:
            with open(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'), 'r') as f:
                draft_data = json.load(f)
            
            # Send the email using the draft data
            mailbox_id = draft_data.get('mailbox_id')
            if mailbox_id and mailbox_id != "none":
                mailboxes = load_mailboxes()
                mailbox = next((mb for mb in mailboxes if mb['id'] == mailbox_id), None)
                if mailbox:
                    success, message = send_authenticated_email(
                        sender_email=mailbox['username'],
                        sender_password=decrypt_password(mailbox['password']),
                        smtp_server=mailbox['smtp_server'],
                        smtp_port=mailbox['smtp_port'],
                        use_tls=mailbox['use_tls'],
                        recipient_email=draft_data["mail_to"],
                        subject=draft_data["subject"],
                        body=draft_data["body"],
                        html_body_path=draft_data.get("html_body_path"),
                        base_path_for_images=os.path.dirname(draft_data["html_body_path"]) if draft_data.get("html_body_path") and os.path.exists(draft_data["html_body_path"]) else (app.config['UPLOAD_FOLDER'] if draft_data["body"].strip().startswith('<html') or re.search(r'<[a-z][\s\S]*>', draft_data["body"]) else None)
                    )
                else:
                    success = False
                    message = "Selected mailbox not found for campaign draft."
            else:
                success, message = send_spoofed_email(
                    mail_from=draft_data["mail_from"],
                    mail_to=draft_data["mail_to"],
                    mail_envelope=draft_data["mail_envelope"],
                    subject=draft_data["subject"],
                    body=draft_data["body"],
                    spoof_domain=draft_data["spoof_domain"],
                    bcc=draft_data.get("bcc") if draft_data.get("bcc") else None,
                    html_body_path=draft_data.get("html_body_path")
                )
            
            # Log the email sending
            log_entry = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'email': f'From: {draft_data["mail_from"]}, To: {draft_data["mail_to"]}, Subject: {draft_data["subject"]}',
                'campaign': campaign_data['name'],
                'success': success,
                'message': message
            }
            
            # Add to log file
            log_data = load_log_data()
            log_data.append(log_entry)
            with open(app.config['LOG_FILE'], 'w') as f:
                json.dump(log_data, f, indent=4)
            
            # Emit socket event
            socketio.emit('log_update', log_entry)
            
            # Add delay between emails if enabled
            if campaign_data.get('delay_emails', False):
                time.sleep(random.randint(5, 30))
        
        except Exception as e:
            print(f"Error sending email from draft {draft_id}: {str(e)}")
            # Log error
            log_entry = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'email': f'Error with draft {draft_id}',
                'campaign': campaign_data['name'],
                'error': str(e),
                'success': False
            }
            log_data = load_log_data()
            log_data.append(log_entry)
            with open(app.config['LOG_FILE'], 'w') as f:
                json.dump(log_data, f, indent=4)
            
            socketio.emit('log_update', log_entry)

def main():
    """Main function to handle both CLI and web server modes"""
    # Check for --web flag
    if '--web' in sys.argv:
        
        print("Starting the web server...")
        print("You can access the web interface at: http://localhost:80")
        print("Press Ctrl+C to stop the web server.")
        socketio.run(app, debug=False, host='0.0.0.0', port=80)
        return
    # If no args provided, show usage
    if len(sys.argv) == 1:
        print("Usage: ./mailspoofsent.py [--bcc bcc_address] --mail-from mail_from --mail-envelope mail_envelope --mail-to mail_to --subject subject --body body [--htmlbody body.html] --spoof-domain domain [--web]")
        return
    
    # Check if running with sudo
    if not is_root():
        print("DISCLAIMER: This script requires sudo rights to run.")
        return 1
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Send spoofed emails')
    parser.add_argument('--bcc', help='Specify a bcc address for the email')
    parser.add_argument('--mail-from', required=True, help='The mail address shown in mail client')
    parser.add_argument('--mail-to', required=True, help="The recipient's email address")
    parser.add_argument('--mail-envelope', required=True, help='The under control mail address to spoof e.g. SPF')
    parser.add_argument('--subject', required=True, help='The subject of the email')
    parser.add_argument('--body', required=True, help='The body of the email')
    parser.add_argument('--htmlbody', help='The HTML body of the email (provide file path)')
    parser.add_argument('--spoof-domain', required=True, help='The domain to spoof from under control of attacker')
    parser.add_argument('--web', action='store_true', help='Start the MailSpoofSent Web UI')
    
    args = parser.parse_args()
    
    # Send the email
    success, message = send_spoofed_email(
        mail_from=args.mail_from,
        mail_to=args.mail_to,
        mail_envelope=args.mail_envelope,
        subject=args.subject,
        body=args.body,
        spoof_domain=args.spoof_domain,
        bcc=args.bcc,
        html_body_path=args.htmlbody
    )
    
    if success:
        print("[+] Email sent successfully!")
        return 0
    else:
        print(f"[-] Failed to send email: {message}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
