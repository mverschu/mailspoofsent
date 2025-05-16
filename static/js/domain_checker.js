// Domain security checker functionality
document.addEventListener('DOMContentLoaded', function() {
    const fromAddressInput = document.getElementById('mail_from');

    // Create a compact status container near the input
    const compactStatusContainer = document.createElement('div');
    compactStatusContainer.className = 'domain-status mt-2';
    fromAddressInput.parentNode.parentNode.appendChild(compactStatusContainer);

    // Add loading spinner
    const spinner = document.createElement('div');
    spinner.className = 'spinner-border spinner-border-sm text-primary me-2 d-none';
    spinner.setAttribute('role', 'status');
    spinner.innerHTML = '<span class="visually-hidden">Loading...</span>';
    compactStatusContainer.appendChild(spinner);

    // Add short status message (just under the From field)
    const statusMessage = document.createElement('span');
    statusMessage.className = 'domain-status-message';
    compactStatusContainer.appendChild(statusMessage);

    // No "View Details" button needed as details are automatically shown in sidebar

    // Find the sidebar element where we'll show the detailed domain info
    const sidebar = document.querySelector('.col-lg-4');

    // Create the domain details card for the sidebar
    const detailsCard = document.createElement('div');
    detailsCard.className = 'card mt-4 d-none';
    detailsCard.id = 'domain-details-card';
    detailsCard.innerHTML = `
        <div class="card-header bg-primary text-white">
            <i class="fas fa-shield-alt me-2"></i> Domain Security Check
        </div>
        <div class="card-body p-0">
            <div id="domain-detail-panel" class="domain-detail-panel p-3">
                <div class="text-center py-4">
                    <i class="fas fa-search fa-2x mb-2 text-muted"></i>
                    <p class="text-muted">Enter an email address to check domain security</p>
                </div>
            </div>
        </div>
    `;

    // Insert the details card after the "Tool Information" card
    sidebar.appendChild(detailsCard);

    // Get reference to the detail panel (inside the card)
    const detailPanel = document.getElementById('domain-detail-panel');

    // Create a debounce function to limit API calls
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Function to check domain security
    function checkDomainSecurity(domain) {
        // Return if domain is empty or doesn't contain @
        if (!domain || !domain.includes('@')) {
            statusMessage.textContent = '';
            spinner.classList.add('d-none');
            detailsCard.classList.add('d-none');
            return;
        }

        // Show loading spinner
        spinner.classList.remove('d-none');
        statusMessage.textContent = 'Checking...';
        statusMessage.className = 'domain-status-message text-info';

        // Extract domain from email
        const domainPart = domain.split('@')[1];

        // Call the API to check domain
        fetch('/api/check-domain', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ domain: domainPart }),
        })
        .then(response => response.json())
        .then(data => {
            // Hide spinner
            spinner.classList.add('d-none');

            // Update compact status message (just under the input)
            const shortMessage = data.spoofable ?
                '✅ Domain can be spoofed' :
                '⚠️ Domain difficult to spoof';
            statusMessage.textContent = shortMessage;
            if (data.spoofable) {
                statusMessage.className = 'domain-status-message text-success fw-bold';
            } else {
                statusMessage.className = 'domain-status-message text-danger fw-bold';
            }

            // Show the details card in sidebar
            detailsCard.classList.remove('d-none');

            // Update detail panel
            let detailsHtml = `<h6 class="mb-2">Security Details for ${domainPart}</h6>`;
            detailsHtml += `<div class="mb-1"><strong>SPF:</strong> ${data.spf.exists ?
                `<span class="text-success">Found</span> - ${data.spf.status}` :
                '<span class="text-danger">Not found</span>'}</div>`;
            detailsHtml += `<div class="mb-1"><strong>DKIM:</strong> ${data.dkim.exists ?
                `<span class="text-success">Found</span> (selector: ${data.dkim.selector})` :
                '<span class="text-warning">Common selectors not found</span>'}</div>`;
            
            // Updated DMARC display to show both main and subdomain policies
            if (data.dmarc.exists) {
                const policyClass = data.dmarc.policy === 'none' ? 'warning' : 'success';
                const policyDisplay = data.dmarc.policy || 'Unknown';
                
                detailsHtml += `<div class="mb-1"><strong>DMARC:</strong> <span class="text-${policyClass}">Found</span>`;
                detailsHtml += ` - Main Policy: ${policyDisplay}`;
                
                // Show subdomain policy if it exists and differs from main policy
                if (data.dmarc.subdomain_policy && data.dmarc.subdomain_policy !== data.dmarc.policy) {
                    const subPolicyClass = data.dmarc.subdomain_policy === 'none' ? 'warning' : 'success';
                    detailsHtml += ` / Subdomain Policy: <span class="text-${subPolicyClass}">${data.dmarc.subdomain_policy}</span>`;
                }
                
                detailsHtml += `</div>`;
            } else {
                detailsHtml += `<div class="mb-1"><strong>DMARC:</strong> <span class="text-danger">Not found</span></div>`;
            }

            // Add record details if they exist
            if (data.spf.record) {
                detailsHtml += `<div class="mt-2 small"><strong>SPF Record:</strong><br><code>${data.spf.record}</code></div>`;
            }
            if (data.dmarc.record) {
                detailsHtml += `<div class="mt-2 small"><strong>DMARC Record:</strong><br><code>${data.dmarc.record}</code></div>`;
            }

            // Recommendation based on domain security
            detailsHtml += `<div class="mt-3 p-2 bg-${data.spoofable ? 'success' : 'danger'} bg-opacity-10 rounded">`;
            if (data.spoofable) {
                detailsHtml += `<strong>✅ This domain can likely be spoofed</strong>`;
                if (data.dmarc.exists && data.dmarc.policy === 'none') {
                    detailsHtml += `<br><small>Note: DMARC exists but is in monitoring mode only`;
                    if (data.dmarc.subdomain_policy && data.dmarc.subdomain_policy !== 'none') {
                        detailsHtml += ` (subdomains have stricter policy: ${data.dmarc.subdomain_policy})`;
                    }
                    detailsHtml += `</small>`;
                }
            } else {
                detailsHtml += `<strong>⚠️ This domain is difficult to spoof</strong><br>`;
                detailsHtml += `<small>Consider using a different sender domain or ensure your mail-envelope domain has proper SPF records</small>`;
            }
            detailsHtml += `</div>`;

            // Add full message from server
            detailsHtml += `<div class="mt-3 small text-muted">${data.message}</div>`;

            detailPanel.innerHTML = detailsHtml;
        })
        .catch(error => {
            // Hide spinner
            spinner.classList.add('d-none');

            // Show error message
            statusMessage.textContent = 'Error checking domain';
            statusMessage.className = 'domain-status-message text-danger';
        });
    }

    // Debounced version to avoid too many API calls while typing
    const debouncedCheckDomain = debounce(checkDomainSecurity, 500);

    // Listen for input changes
    fromAddressInput.addEventListener('input', function() {
        debouncedCheckDomain(this.value);
    });

    // Also check when the page loads if there's already a value
    if (fromAddressInput.value) {
        debouncedCheckDomain(fromAddressInput.value);
    }

    // When the mail_envelope field is changed, recommend using the same domain as the spoofed domain
    const mailEnvelopeInput = document.getElementById('mail_envelope');
    const spoofDomainInput = document.getElementById('spoof_domain');

    mailEnvelopeInput.addEventListener('change', function() {
        const envelopeValue = this.value;
        if (envelopeValue && envelopeValue.includes('@')) {
            const envelopeDomain = envelopeValue.split('@')[1];
            if (spoofDomainInput.value === '') {
                spoofDomainInput.value = envelopeDomain;
            }
        }
    });
});
