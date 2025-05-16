// JavaScript for MailSpoofSent
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Socket.io connection
    const socket = io();
    
    // Listen for log updates
    socket.on('log_update', function(data) {
        const logContainer = document.getElementById('log-container');
        if (logContainer) {
            // Add the new log entry at the top
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry p-2 border-bottom';
            logEntry.innerHTML = `
                <div class="d-flex justify-content-between">
                    <span class="fw-bold">${data.email}</span>
                    <span class="log-timestamp">${data.timestamp}</span>
                </div>
            `;
            logContainer.prepend(logEntry);
            
            // Show notification
            showNotification('Email Sent', `${data.email}`, 'success');
        }
    });
    
    // Function to show notifications
    window.showNotification = function(title, message, type) {
        // Create toast container if it doesn't exist
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `custom-toast ${type}`;
        toast.innerHTML = `
            <div class="toast-header bg-${type === 'success' ? 'success' : 'danger'} text-white">
                <strong class="me-auto">${title}</strong>
                <button type="button" class="btn-close btn-close-white" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;
        
        // Add to container
        toastContainer.appendChild(toast);
        
        // Show toast
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Auto hide after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 5000);
    };
    
    // Save draft functionality
    const saveDraftBtn = document.getElementById('save-draft-btn');
    if (saveDraftBtn) {
        saveDraftBtn.addEventListener('click', function() {
            const form = document.getElementById('email-form');
            const formData = new FormData(form);
            formData.append('draft_id', generateDraftId());
            
            fetch('/drafts', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (response.ok) {
                    showNotification('Success', 'Draft saved successfully!', 'success');
                }
            })
            .catch(error => {
                showNotification('Error', 'Failed to save draft.', 'error');
                console.error('Error:', error);
            });
        });
    }
    
    // Generate a unique ID for drafts
    function generateDraftId() {
        return 'draft_' + Date.now();
    }
    
    // Load draft functionality
    const draftItems = document.querySelectorAll('.draft-item');
    draftItems.forEach(item => {
        item.addEventListener('click', function() {
            const draftId = this.getAttribute('data-draft-id');
            fetch(`/draft/${draftId}`)
                .then(response => response.json())
                .then(data => {
                    // Fill the form with draft data
                    document.querySelector('[name="mail_from"]').value = data.mail_from;
                    document.querySelector('[name="mail_to"]').value = data.mail_to;
                    document.querySelector('[name="mail_envelope"]').value = data.mail_envelope;
                    document.querySelector('[name="subject"]').value = data.subject;
                    document.querySelector('[name="body"]').value = data.body;
                    document.querySelector('[name="spoof_domain"]').value = data.spoof_domain;
                    
                    showNotification('Success', 'Draft loaded successfully!', 'success');
                })
                .catch(error => {
                    showNotification('Error', 'Failed to load draft.', 'error');
                    console.error('Error:', error);
                });
        });
    });
    
    // HTML editor integration (if exists)
    const htmlEditor = document.getElementById('html-editor');
    if (htmlEditor) {
        // Simple logic to sync content with hidden textarea
        const bodyInput = document.getElementById('body-input');
        htmlEditor.addEventListener('input', function() {
            bodyInput.value = this.innerHTML;
        });
    }
});
