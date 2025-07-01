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
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast ${type === 'success' ? 'bg-success text-white' : 'bg-danger text-white'}`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        toast.innerHTML = `
            <div class="toast-header ${type === 'success' ? 'bg-success text-white' : 'bg-danger text-white'}">
                <strong class="me-auto">${title}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;
        
        // Add to container
        toastContainer.appendChild(toast);
        
        // Initialize and show the toast
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 5000
        });
        bsToast.show();
        
        // Remove the toast after it's hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    };
    
    // Modal helper functions
    window.showModal = function(modalId) {
        const modalElement = document.getElementById(modalId);
        if (!modalElement) return;
        
        try {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        } catch (error) {
            console.error('Error showing modal:', error);
            // Fallback manual approach
            modalElement.classList.add('show');
            modalElement.style.display = 'block';
            document.body.classList.add('modal-open');
            
            // Add backdrop
            const backdrop = document.createElement('div');
            backdrop.className = 'modal-backdrop fade show';
            document.body.appendChild(backdrop);
        }
    };
    
    window.hideModal = function(modalId) {
        const modalElement = document.getElementById(modalId);
        if (!modalElement) return;
        
        try {
            const modalInstance = bootstrap.Modal.getInstance(modalElement);
            if (modalInstance) {
                modalInstance.hide();
            } else {
                // Fallback manual approach
                modalElement.classList.remove('show');
                modalElement.style.display = 'none';
                document.body.classList.remove('modal-open');
                document.querySelector('.modal-backdrop')?.remove();
            }
        } catch (error) {
            console.error('Error hiding modal:', error);
            // Fallback manual approach
            modalElement.classList.remove('show');
            modalElement.style.display = 'none';
            document.body.classList.remove('modal-open');
            document.querySelector('.modal-backdrop')?.remove();
        }
    };
    
    // Save draft functionality
    const saveDraftBtn = document.getElementById('save-draft-btn');
    if (saveDraftBtn) {
        saveDraftBtn.addEventListener('click', function() {
            // Show the modal
            const draftNameModal = new bootstrap.Modal(document.getElementById('draftNameModal'));
            draftNameModal.show();
        });
    }

    const confirmSaveDraftBtn = document.getElementById('confirmSaveDraftBtn');
    if (confirmSaveDraftBtn) {
        confirmSaveDraftBtn.addEventListener('click', function() {
            const draftNameInput = document.getElementById('draftNameInput');
            const draftName = draftNameInput.value.trim();

            if (!draftName) {
                alert('Please enter a draft name.');
                return;
            }

            const form = document.getElementById('email-form');
            const formData = new FormData(form);
            formData.append('draft_id', generateDraftId());
            formData.append('draft_name', draftName); // Add the draft name

            fetch('/drafts', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Failed to save draft');
                }
            })
            .then(data => {
                if (data.success) {
                    showNotification('Success', 'Draft saved successfully!', 'success');
                    
                    // Update draft ID
                    document.getElementById('draft_id').value = data.draft_id;
                    
                    // Add to dropdown if needed
                    const draftSelect = document.getElementById('draft_select');
                    if (draftSelect) {
                        let exists = false;
                        for (let i = 0; i < draftSelect.options.length; i++) {
                            if (draftSelect.options[i].value === data.draft_id) {
                                exists = true;
                                break;
                            }
                        }
                        
                        if (!exists) {
                            const option = document.createElement('option');
                            option.value = data.draft_id;
                            option.text = draftName; // Use the provided draft name
                            draftSelect.appendChild(option);
                            draftSelect.value = data.draft_id;
                        }
                    }
                    // Hide the modal
                    const draftNameModal = bootstrap.Modal.getInstance(document.getElementById('draftNameModal'));
                    draftNameModal.hide();
                    draftNameInput.value = ''; // Clear the input
                } else {
                    throw new Error(data.error || 'Failed to save draft');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error saving draft: ' + error.message);
            });
        });
    }
    
    // Generate a unique ID for drafts
    function generateDraftId() {
        return 'draft_' + Date.now();
    }
    
    // Draft selection
    const draftSelect = document.getElementById('draft_select');
    if (draftSelect) {
        draftSelect.addEventListener('change', function() {
            const draftId = this.value;
            if (!draftId) return;
            
            fetch(`/draft/${draftId}`)
                .then(response => response.json())
                .then(data => {
                    // Fill the form with draft data
                    document.querySelector('[name="mail_from"]').value = data.mail_from || '';
                    document.querySelector('[name="mail_to"]').value = data.mail_to || '';
                    document.querySelector('[name="mail_envelope"]').value = data.mail_envelope || '';
                    document.querySelector('[name="subject"]').value = data.subject || '';
                    document.querySelector('[name="body"]').value = data.body || '';
                    document.querySelector('[name="spoof_domain"]').value = data.spoof_domain || '';
                    document.querySelector('[name="bcc"]').value = data.bcc || '';
                    document.getElementById('draft_id').value = draftId;
                    
                    // Update iframe if it's active
                    const htmlEditorFrame = document.getElementById('html-editor-frame');
                    if (htmlEditorFrame && document.getElementById('visual-body').classList.contains('show')) {
                        try {
                            const iframeDoc = htmlEditorFrame.contentDocument || htmlEditorFrame.contentWindow.document;
                            
                            // Create base HTML structure with content
                            iframeDoc.open();
                            iframeDoc.write(`
                                <!DOCTYPE html>
                                <html>
                                <head>
                                    <meta charset="UTF-8">
                                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                    <style>
                                        body {
                                            font-family: Arial, sans-serif;
                                            padding: 10px;
                                            margin: 0;
                                            line-height: 1.6;
                                        }
                                        img { max-width: 100%; height: auto; }
                                        table { max-width: 100%; }
                                    </style>
                                </head>
                                <body contenteditable="true">${data.body || ''}</body>
                                </html>
                            `);
                            iframeDoc.close();
                            
                            // Add event listener to sync changes
                            iframeDoc.body.addEventListener('input', function() {
                                document.querySelector('[name="body"]').value = iframeDoc.body.innerHTML;
                            });
                        } catch (e) {
                            console.error('Error updating iframe:', e);
                        }
                    }
                    
                })
                .catch(error => {
                    showNotification('Error', 'Failed to load draft', 'error');
                    console.error('Error:', error);
                });
        });
    }
    
    // Template selection
    const templateSelect = document.getElementById('template_select');
    if (templateSelect) {
        templateSelect.addEventListener('change', function() {
            const templateId = this.value;
            if (!templateId) return;
            
            fetch(`/templates/${templateId}`)
                .then(response => response.json())
                .then(data => {
                    // Fill the form with template data
                    document.querySelector('[name="subject"]').value = data.subject || '';
                    document.querySelector('[name="body"]').value = data.body || '';
                    
                    // Update iframe if it's active
                    const htmlEditorFrame = document.getElementById('html-editor-frame');
                    if (htmlEditorFrame && document.getElementById('visual-body').classList.contains('show')) {
                        try {
                            const iframeDoc = htmlEditorFrame.contentDocument || htmlEditorFrame.contentWindow.document;
                            
                            // Create base HTML structure with content
                            iframeDoc.open();
                            iframeDoc.write(`
                                <!DOCTYPE html>
                                <html>
                                <head>
                                    <meta charset="UTF-8">
                                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                    <style>
                                        body {
                                            font-family: Arial, sans-serif;
                                            padding: 10px;
                                            margin: 0;
                                            line-height: 1.6;
                                        }
                                        img { max-width: 100%; height: auto; }
                                        table { max-width: 100%; }
                                    </style>
                                </head>
                                <body contenteditable="true">${data.body || ''}</body>
                                </html>
                            `);
                            iframeDoc.close();
                            
                            // Add event listener to sync changes
                            iframeDoc.body.addEventListener('input', function() {
                                document.querySelector('[name="body"]').value = iframeDoc.body.innerHTML;
                            });
                        } catch (e) {
                            console.error('Error updating iframe:', e);
                        }
                    }
                    
                    showNotification('Success', `Template "${data.name}" loaded successfully!`, 'success');
                })
                .catch(error => {
                    showNotification('Error', 'Failed to load template', 'error');
                    console.error('Error:', error);
                });
        });
        
        // Auto-load template if specified in URL
        const urlParams = new URLSearchParams(window.location.search);
        const templateId = urlParams.get('template_id');
        if (templateId) {
            templateSelect.value = templateId;
            templateSelect.dispatchEvent(new Event('change'));
        }
    }
    
    // Visual editor iframe integration
    const visualTab = document.getElementById('visual-tab');
    const htmlEditorFrame = document.getElementById('html-editor-frame');
    const bodyInput = document.querySelector('[name="body"]');
    
    if (visualTab && htmlEditorFrame && bodyInput) {
        visualTab.addEventListener('click', function() {
            try {
                const iframeDoc = htmlEditorFrame.contentDocument || htmlEditorFrame.contentWindow.document;
                
                // Create base HTML structure with content
                iframeDoc.open();
                iframeDoc.write(`
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <style>
                            body {
                                font-family: Arial, sans-serif;
                                padding: 10px;
                                margin: 0;
                                line-height: 1.6;
                                min-height: 100%;
                            }
                            img { max-width: 100%; height: auto; }
                            table { max-width: 100%; }
                        </style>
                    </head>
                    <body contenteditable="true">${bodyInput.value}</body>
                    </html>
                `);
                iframeDoc.close();
                
                // Add event listener to sync changes
                iframeDoc.body.addEventListener('input', function() {
                    bodyInput.value = iframeDoc.body.innerHTML;
                });
            } catch (e) {
                console.error('Error initializing iframe editor:', e);
            }
        });
        
        // Sync from iframe to textarea when switching back to text tab
        document.getElementById('text-tab')?.addEventListener('click', function() {
            try {
                const iframeDoc = htmlEditorFrame.contentDocument || htmlEditorFrame.contentWindow.document;
                if (iframeDoc && iframeDoc.body) {
                    bodyInput.value = iframeDoc.body.innerHTML;
                }
            } catch (e) {
                console.error('Error syncing from iframe to textarea:', e);
            }
        });
    }
    
    // Clear form button
    const clearFormBtn = document.getElementById('clear-form-btn');
    if (clearFormBtn) {
        clearFormBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to clear the form?')) {
                document.getElementById('email-form').reset();
                
                // Reset selects
                if (templateSelect) templateSelect.value = '';
                if (draftSelect) draftSelect.value = '';
                
                // Generate new draft ID
                document.getElementById('draft_id').value = generateDraftId();
                
                // Reset iframe if active
                if (htmlEditorFrame && document.getElementById('visual-body').classList.contains('show')) {
                    try {
                        const iframeDoc = htmlEditorFrame.contentDocument || htmlEditorFrame.contentWindow.document;
                        iframeDoc.body.innerHTML = '';
                    } catch (e) {
                        console.error('Error clearing iframe:', e);
                    }
                }
                
                showNotification('Info', 'Form cleared', 'success');
            }
        });
    }

    // Mailbox selection logic
    const mailFromSelect = document.getElementById('mail_from');
    const mailFromCustomInput = document.getElementById('mail_from_custom');

    if (mailFromSelect && mailFromCustomInput) {
        mailFromSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                mailFromCustomInput.style.display = 'block';
                mailFromCustomInput.setAttribute('name', 'mail_from'); // Use this for form submission
                mailFromCustomInput.setAttribute('required', 'true');
                this.removeAttribute('name'); // Remove name from select so it's not submitted
                this.removeAttribute('required');
            } else {
                mailFromCustomInput.style.display = 'none';
                mailFromCustomInput.removeAttribute('name');
                mailFromCustomInput.removeAttribute('required');
                this.setAttribute('name', 'mail_from'); // Use this for form submission
                this.setAttribute('required', 'true');
            }
        });

        // Initialize state based on current selection (if any)
        if (mailFromSelect.value === 'custom') {
            mailFromCustomInput.style.display = 'block';
            mailFromCustomInput.setAttribute('name', 'mail_from');
            mailFromCustomInput.setAttribute('required', 'true');
            mailFromSelect.removeAttribute('name');
            mailFromSelect.removeAttribute('required');
        } else {
            mailFromCustomInput.style.display = 'none';
            mailFromCustomInput.removeAttribute('name');
            mailFromCustomInput.removeAttribute('required');
            mailFromSelect.setAttribute('name', 'mail_from');
            mailFromSelect.setAttribute('required', 'true');
        }
    }
});