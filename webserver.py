#!/usr/bin/env python3

from flask import Flask, render_template, request
import subprocess
import shlex

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('form.html')

@app.route('/send-email', methods=['POST'])
def send_email():
    # Extract the form data
    mail_from = request.form['mail_from']
    mail_to = request.form['mail_to']
    mail_envelope = request.form['mail_envelope']
    subject = request.form['subject']
    body = request.form['body']
    spoof_domain = request.form['spoof_domain']

    # Construct the shell command
    command = f'./mailspoofsent.sh --mail-from "{mail_from}" --mail-to "{mail_to}" --mail-envelope "{mail_envelope}" --subject "{subject}" --body "{body}" --spoof-domain "{spoof_domain}"'

    # Execute the shell command and wait for it to complete
    subprocess.run(shlex.split(command))

    # Redirect back to the home page
    return render_template('form.html')

if __name__ == '__main__':
    app.run(debug=True)
