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
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

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
def send_spoofed_email(mail_from, mail_to, mail_envelope, subject, body, spoof_domain, bcc=None, html_body_path=None):
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
    drafts = [f.replace('.json', '') for f in os.listdir(app.config['DRAFTS_FOLDER']) 
              if f.endswith('.json')]
    
    # Current timestamp for draft ID
    current_time = time.time()
    now_timestamp = int(current_time * 1000)
    
    return render_template('index.html', log_data=log_data, templates=templates, 
                          drafts=drafts, current_time=current_time, now_timestamp=now_timestamp)

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
    
    # Handle HTML body file upload
    html_file = request.files.get('html_body')
    html_body_path = ''
    if html_file and html_file.filename:
        html_body_path = os.path.join(app.config['UPLOAD_FOLDER'], html_file.filename)
        html_file.save(html_body_path)
    
    # Send the email
    success, message = send_spoofed_email(
        mail_from=mail_from,
        mail_to=mail_to,
        mail_envelope=mail_envelope,
        subject=subject,
        body=body,
        spoof_domain=spoof_domain,
        bcc=bcc if bcc else None,
        html_body_path=html_body_path if html_body_path else None
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
    
    # Redirect based on request type
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'template_id': template_id})
    return redirect(url_for('manage_templates'))

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
    
    # Redirect based on request type
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    return redirect(url_for('manage_templates'))

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
            'bcc': request.form.get('bcc', '')
        }
        
        draft_id = request.form['draft_id']
        with open(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'), 'w') as f:
            json.dump(draft_data, f, indent=4)
        
        # If Ajax request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'draft_id': draft_id})
        
    # List all drafts
    drafts = [f for f in os.listdir(app.config['DRAFTS_FOLDER']) if f.endswith('.json')]
    return render_template('drafts.html', drafts=drafts)

@app.route('/draft/<draft_id>', methods=['GET'])
def get_draft(draft_id):
    """API to get draft details"""
    try:
        with open(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'), 'r') as f:
            draft_data = json.load(f)
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

def execute_campaign(campaign_id, campaign_data):
    """Execute all emails in a campaign"""
    for draft_id in campaign_data['draft_ids']:
        try:
            with open(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'), 'r') as f:
                draft_data = json.load(f)
            
            # Send the email using the draft data
            success, message = send_spoofed_email(
                mail_from=draft_data["mail_from"],
                mail_to=draft_data["mail_to"],
                mail_envelope=draft_data["mail_envelope"],
                subject=draft_data["subject"],
                body=draft_data["body"],
                spoof_domain=draft_data["spoof_domain"],
                bcc=draft_data.get("bcc") if draft_data.get("bcc") else None
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

# Add example templates if template folder is empty
def add_example_templates():
    """Add example templates if the templates folder is empty"""
    if not os.listdir(app.config['TEMPLATES_FOLDER']):
        print("Adding example templates...")
        
        # Example 1: Password Reset Request
        password_reset = {
            "name": "Password Reset Request",
            "description": "Fake password reset request template for phishing tests",
            "subject": "URGENT: Your Account Password Reset Request",
            "body": "<html><head><style>body{font-family:Arial,sans-serif;line-height:1.6;color:#333}a{color:#0066cc}a.button{display:inline-block;padding:10px 20px;background-color:#0066cc;color:white;text-decoration:none;border-radius:4px;font-weight:bold}.header{padding:20px;background-color:#f8f8f8;border-bottom:1px solid #ddd}.footer{margin-top:40px;padding:20px;background-color:#f8f8f8;border-top:1px solid #ddd;font-size:12px;color:#666}.logo{max-height:50px}.container{max-width:600px;margin:0 auto;padding:20px}</style></head><body><div class='container'><div class='header'><img src='https://via.placeholder.com/150x50' alt='Company Logo' class='logo'></div><h2>Password Reset Request</h2><p>Dear Valued Customer,</p><p>We've received a request to reset your password. If you did not request this change, please ignore this email and your account will remain secure.</p><p>To reset your password, please click on the button below:</p><p style='text-align:center;margin:30px 0'><a href='https://account-verification.example.com/reset?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' class='button'>Reset Password</a></p><p>This link will expire in 24 hours for security reasons.</p><p>If the button above doesn't work, please copy and paste the following URL into your browser:</p><p><a href='https://account-verification.example.com/reset?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'>https://account-verification.example.com/reset?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9</a></p><p>If you didn't request a password reset, please contact our security team immediately at security@example.com.</p><p>Regards,<br>The Security Team</p><div class='footer'><p>This email was sent to you as a registered user of our service. Please do not reply to this message; it was sent from an unmonitored email address.</p><p>&copy; 2025 Example Company. All rights reserved.</p></div></div></body></html>",
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Example 2: IT Security Update
        it_security = {
            "name": "IT Security Update Required",
            "description": "Fake IT security update notification template for phishing tests",
            "subject": "IMPORTANT: Security Update Required for Your Corporate Account",
            "body": "<html><head><style>body{font-family:Arial,sans-serif;line-height:1.6;color:#333}a{color:#0066cc}a.button{display:inline-block;padding:10px 20px;background-color:#28a745;color:white;text-decoration:none;border-radius:4px;font-weight:bold}.header{padding:20px;background-color:#f8f8f8;border-bottom:1px solid #ddd}.footer{margin-top:40px;padding:20px;background-color:#f8f8f8;border-top:1px solid #ddd;font-size:12px;color:#666}.logo{max-height:50px}.container{max-width:600px;margin:0 auto;padding:20px}.alert{background-color:#fff3cd;border:1px solid #ffeeba;padding:15px;margin:20px 0;border-radius:4px;color:#856404}</style></head><body><div class='container'><div class='header'><img src='https://via.placeholder.com/150x50' alt='Company Logo' class='logo'></div><h2>Important Security Update Required</h2><div class='alert'><strong>Security Notice:</strong> Our systems have detected that your account security needs to be updated immediately.</div><p>Dear Team Member,</p><p>The IT Security Department has identified that your corporate account requires an urgent security update to protect against recent cyber threats targeting our organization.</p><p><strong>Action Required:</strong> Please authenticate and update your account security settings by clicking the secure link below:</p><p style='text-align:center;margin:30px 0'><a href='https://security-verification.example.com/update?employee=user123' class='button'>Update Security Settings</a></p><p>This security update includes:</p><ul><li>Enhanced password protection</li><li>Multi-factor authentication reconfiguration</li><li>Security question updates</li><li>Device verification</li></ul><p><strong>DEADLINE:</strong> Please complete this update within 24 hours to maintain access to company resources.</p><p>If you have any questions or need assistance, please contact the IT Help Desk at helpdesk@example.com or ext. 5555.</p><p>Thank you for your prompt attention to this security matter.</p><p>Regards,<br>IT Security Department</p><div class='footer'><p>This is an automated system email. Please do not reply to this message.</p><p>&copy; 2025 Example Corporation. All rights reserved.</p><p><small>IT-SEC-2025-05-17-01</small></p></div></div></body></html>",
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Save the example templates
        template1_id = f"template_{int(time.time() * 1000)}"
        template2_id = f"template_{int(time.time() * 1000) + 1}"
        
        with open(os.path.join(app.config['TEMPLATES_FOLDER'], f'{template1_id}.json'), 'w') as f:
            json.dump(password_reset, f, indent=4)
            
        with open(os.path.join(app.config['TEMPLATES_FOLDER'], f'{template2_id}.json'), 'w') as f:
            json.dump(it_security, f, indent=4)

def main():
    """Main function to handle both CLI and web server modes"""
    # Check for --web flag
    if '--web' in sys.argv:
        # Add example templates if needed
        add_example_templates()
        
        print("Starting the web server...")
        print("You can access the web interface at: http://localhost:80")
        print("Press Ctrl+C to stop the web server.")
        socketio.run(app, debug=True, host='0.0.0.0', port=80)
        return
    # Check for --web flag
    if '--web' in sys.argv:
        print("Starting the web server...")
        print("You can access the web interface at: http://localhost:80")
        print("Press Ctrl+C to stop the web server.")
        socketio.run(app, debug=True, host='0.0.0.0', port=80)
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
    parser.add_argument('--mail-to', required=True, help='The recipient\'s email address')
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
