#!/usr/bin/env python3
import dns.resolver
import json
import re
from flask import Blueprint, request, jsonify

# Create Blueprint for domain checker API
domain_checker = Blueprint('domain_checker', __name__)

@domain_checker.route('/api/check-domain', methods=['POST'])
def check_domain():
    """API endpoint to check domain security configurations"""
    try:
        data = request.get_json()
        if not data or 'domain' not in data:
            return jsonify({'error': 'No domain provided'}), 400
            
        domain = data['domain']
        
        # Initialize results
        results = {
            'domain': domain,
            'spf': {'exists': False, 'record': None, 'status': 'unknown'},
            'dkim': {'exists': False, 'record': None, 'status': 'unknown'},
            'dmarc': {'exists': False, 'record': None, 'status': 'unknown', 'policy': None, 'subdomain_policy': None},
            'spoofable': True,
            'message': "Checking domain security..."
        }
        
        # Check SPF record
        try:
            spf_records = dns.resolver.resolve(domain, 'TXT')
            for record in spf_records:
                txt_record = record.to_text().strip('"')
                if txt_record.startswith('v=spf1'):
                    results['spf']['exists'] = True
                    results['spf']['record'] = txt_record
                    results['spf']['status'] = 'found'
                    if ' -all' in txt_record:
                        results['spf']['status'] = 'strict'
                    elif ' ~all' in txt_record:
                        results['spf']['status'] = 'moderate'
                    elif ' ?all' in txt_record:
                        results['spf']['status'] = 'neutral'
                    break
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
            results['spf']['status'] = 'not found'
        
        # Check common DKIM selectors
        common_selectors = ['default', 'dkim', 'mail', 'selector1', 'selector2', 'google', 'k1']
        for selector in common_selectors:
            try:
                dkim_domain = f"{selector}._domainkey.{domain}"
                dkim_records = dns.resolver.resolve(dkim_domain, 'TXT')
                results['dkim']['exists'] = True
                results['dkim']['record'] = dkim_records[0].to_text().strip('"')
                results['dkim']['status'] = 'found'
                results['dkim']['selector'] = selector
                break
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
                continue
                
        # Check DMARC record
        try:
            dmarc_domain = f"_dmarc.{domain}"
            dmarc_records = dns.resolver.resolve(dmarc_domain, 'TXT')
            for record in dmarc_records:
                txt_record = record.to_text().strip('"')
                if txt_record.startswith('v=DMARC1'):
                    results['dmarc']['exists'] = True
                    results['dmarc']['record'] = txt_record
                    results['dmarc']['status'] = 'found'
                    
                    # Extract main DMARC policy using regex to match exact p= tag
                    p_match = re.search(r'p\s*=\s*(none|quarantine|reject)', txt_record)
                    if p_match:
                        results['dmarc']['policy'] = p_match.group(1)
                    
                    # Extract subdomain DMARC policy using regex to match exact sp= tag
                    sp_match = re.search(r'sp\s*=\s*(none|quarantine|reject)', txt_record)
                    if sp_match:
                        results['dmarc']['subdomain_policy'] = sp_match.group(1)
                    else:
                        # If no sp= tag is found, subdomain policy inherits from main policy
                        results['dmarc']['subdomain_policy'] = results['dmarc']['policy']
                    
                    break
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException):
            results['dmarc']['status'] = 'not found'
        
        # Determine if domain is spoofable - only use the main policy (p=), not the subdomain policy (sp=)
        if results['dmarc']['exists'] and results['dmarc']['policy'] in ['reject', 'quarantine']:
            results['spoofable'] = False
            results['message'] = f"⚠️ DIFFICULT TO SPOOF: Domain has DMARC with p={results['dmarc']['policy']}"
        elif results['dmarc']['exists'] and results['dmarc']['policy'] == 'none':
            results['spoofable'] = True
            results['message'] = "✅ SPOOFING POSSIBLE: DMARC exists but policy=none (monitoring only)"
            if results['dmarc']['subdomain_policy'] in ['reject', 'quarantine']:
                results['message'] += f" (Note: subdomains have stricter policy: sp={results['dmarc']['subdomain_policy']})"
        elif results['spf']['exists'] and results['spf']['status'] == 'strict':
            results['spoofable'] = True
            results['message'] = "⚠️ SPF PROTECTED: Domain has strict SPF but no enforced DMARC"
        elif not results['spf']['exists'] and not results['dmarc']['exists']:
            results['spoofable'] = True
            results['message'] = "✅ EASY TO SPOOF: No SPF or DMARC found"
        else:
            results['spoofable'] = True
            results['message'] = "✅ SPOOFING POSSIBLE: Domain has minimal email security"
            
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def register_routes(app):
    """Register the domain checker blueprint with the Flask app"""
    app.register_blueprint(domain_checker)
