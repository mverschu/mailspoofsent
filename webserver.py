#!/usr/bin/env python3

import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import subprocess
import shlex
import json
from datetime import datetime
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DRAFTS_FOLDER'] = 'drafts'
app.config['CAMPAIGNS_FOLDER'] = 'campaigns'
app.config['LOG_FILE'] = 'log.json'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DRAFTS_FOLDER'], exist_ok=True)
os.makedirs(app.config['CAMPAIGNS_FOLDER'], exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/send-email', methods=['POST'])
def send_email():
    mail_from = request.form['mail_from']
    mail_to = request.form['mail_to']
    mail_envelope = request.form['mail_envelope']
    subject = request.form['subject']
    body = request.form.get('body', '')
    spoof_domain = request.form['spoof_domain']
    html_file = request.files.get('html_body')

    html_body_path = ''
    if html_file:
        html_body_path = os.path.join(app.config['UPLOAD_FOLDER'], html_file.filename)
        html_file.save(html_body_path)

    command = f'./mailspoofsent.sh --mail-from "{mail_from}" --mail-to "{mail_to}" --mail-envelope "{mail_envelope}" --subject "{subject}" --body "{body}" --spoof-domain "{spoof_domain}"'
    
    if html_body_path:
        command += f' --htmlbody "{html_body_path}"'

    subprocess.run(shlex.split(command))

    log_entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'email': f'From: {mail_from}, To: {mail_to}, Subject: {subject}'
    }

    if os.path.exists(app.config['LOG_FILE']):
        with open(app.config['LOG_FILE'], 'r') as f:
            log_data = json.load(f)
    else:
        log_data = []

    log_data.append(log_entry)
    with open(app.config['LOG_FILE'], 'w') as f:
        json.dump(log_data, f)

    socketio.emit('log_update', log_entry)

    return redirect(url_for('home'))

@app.route('/log', methods=['GET'])
def log():
    if os.path.exists(app.config['LOG_FILE']):
        with open(app.config['LOG_FILE'], 'r') as f:
            log_data = json.load(f)
    else:
        log_data = []

    return jsonify({'log': log_data})

@app.route('/drafts', methods=['GET', 'POST'])
def manage_drafts():
    if request.method == 'POST':
        draft_data = {
            'mail_from': request.form['mail_from'],
            'mail_to': request.form['mail_to'],
            'mail_envelope': request.form['mail_envelope'],
            'subject': request.form['subject'],
            'body': request.form.get('body', ''),
            'spoof_domain': request.form['spoof_domain'],
        }
        draft_id = request.form['draft_id']
        with open(os.path.join(app.config['DRAFTS_FOLDER'], f'{draft_id}.json'), 'w') as f:
            json.dump(draft_data, f)

    drafts = [f for f in os.listdir(app.config['DRAFTS_FOLDER']) if f.endswith('.json')]
    return render_template('drafts.html', drafts=drafts)

@app.route('/campaigns', methods=['GET', 'POST'])
def manage_campaigns():
    if request.method == 'POST':
        campaign_data = {
            'name': request.form['campaign_name'],
            'draft_ids': request.form.getlist('draft_ids')
        }
        campaign_id = request.form['campaign_id']
        with open(os.path.join(app.config['CAMPAIGNS_FOLDER'], f'{campaign_id}.json'), 'w') as f:
            json.dump(campaign_data, f)

    campaigns = [f for f in os.listdir(app.config['CAMPAIGNS_FOLDER']) if f.endswith('.json')]
    drafts = [f for f in os.listdir(app.config['DRAFTS_FOLDER']) if f.endswith('.json')]
    return render_template('campaigns.html', campaigns=campaigns, drafts=drafts)

if __name__ == '__main__':
    socketio.run(app, debug=True)
