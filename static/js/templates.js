// JavaScript for Template Functionality
document.addEventListener('DOMContentLoaded', function() {
    // Template editing and management
    initTemplateManagement();
    
    // Template selection in email composer
    initTemplateSelection();
    
    // Draft operations
    initDraftOperations();
});

function initTemplateManagement() {
    // Template preview functionality
    const previewButtons = document.querySelectorAll('.preview-template');
    if (previewButtons.length > 0) {
        previewButtons.forEach(button => {
            button.addEventListener('click', function() {
                const templateId = this.getAttribute('data-template-id');
                previewTemplate(templateId);
            });
        });
    }
    
    // Template editing functionality
    const editButtons = document.querySelectorAll('.edit-template');
    if (editButtons.length > 0) {
        editButtons.forEach(button => {
            button.addEventListener('click', function() {
                const templateId = this.getAttribute('data-template-id');
                loadTemplateForEditing(templateId);
            });
        });
    }
    
    // Template deletion functionality
    const deleteButtons = document.querySelectorAll('.delete-template');
    if (deleteButtons.length > 0) {
        deleteButtons.forEach(button => {
            button.addEventListener('click', function() {
                const templateId = this.getAttribute('data-template-id');
                const templateName = this.getAttribute('data-template-name');
                confirmDeleteTemplate(templateId, templateName);
            });
        });
    }
    
    // Visual editor sync for create form
    const templateHtmlEditor = document.getElementById('template-html-editor');
    const templateBodyInput = document.getElementById('template-body-input');
    
    if (templateHtmlEditor && templateBodyInput) {
        templateHtmlEditor.addEventListener('input', function() {
            templateBodyInput.value = this.innerHTML;
        });
        
        // Set up tab switching for visual editor
        document.getElementById('template-visual-tab')?.addEventListener('click', function() {
            templateHtmlEditor.innerHTML = templateBodyInput.value;
        });
        
        document.getElementById('template-text-tab')?.addEventListener('click', function() {
            templateBodyInput.value = templateHtmlEditor.innerHTML;
        });
    }
    
    // Visual editor sync for edit form
    const editTemplateHtmlEditor = document.getElementById('edit-template-html-editor');
    const editTemplateBodyInput = document.getElementById('edit-template-body-input');
    
    if (editTemplateHtmlEditor && editTemplateBodyInput) {
        editTemplateHtmlEditor.addEventListener('input', function() {
            editTemplateBodyInput.value = this.innerHTML;
        });
        
        // Set up tab switching for edit visual editor
        document.getElementById('edit-template-visual-tab')?.addEventListener('click', function() {
            editTemplateHtmlEditor.innerHTML = editTemplateBodyInput.value;
        });
        
        document.getElementById('edit-template-text-tab')?.addEventListener('click', function() {
            editTemplateBodyInput.value = editTemplateHtmlEditor.innerHTML;
        });
    }
    
    // Create template form
    const createTemplateForm = document.getElementById('create-template-form');
    if (createTemplateForm) {
        createTemplateForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            
            fetch(this.action, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Hide modal
                    const modal = bootstrap.Modal.getInstance(document.getElementById('createTemplateModal'));
                    modal.hide();
                    
                    // Show success notification
                    showNotification('Success', 'Template created successfully', 'success');
                    
                    // Reload page after short delay
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
            })
            .catch(error => {
                console.error('Error creating template:', error);
                showNotification('Error', 'Failed to create template', 'error');
            });
        });
    }
    
    // Edit template form
    const editTemplateForm = document.getElementById('edit-template-form');
    if (editTemplateForm) {
        editTemplateForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            
            fetch(this.action, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Hide modal
                    const modal = bootstrap.Modal.getInstance(document.getElementById('editTemplateModal'));
                    modal.hide();
                    
                    // Show success notification
                    showNotification('Success', 'Template updated successfully', 'success');
                    
                    // Reload page after short delay
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
            })
            .catch(error => {
                console.error('Error updating template:', error);
            });
        });
    }
}

function initTemplateSelection() {
    // Template selection in email composition form
    const templateSelect = document.getElementById('template_select');
    if (templateSelect) {
        templateSelect.addEventListener('change', function() {
            const templateId = this.value;
            if (!templateId) return;
            
            loadTemplateIntoForm(templateId);
        });
        
        // Auto-load template if specified in URL
        const urlParams = new URLSearchParams(window.location.search);
        const templateId = urlParams.get('template_id');
        if (templateId) {
            templateSelect.value = templateId;
            
            // Only load the template, don't trigger the change event
            // to avoid duplicate notifications
            loadTemplateIntoForm(templateId, false);
        }
    }
}

function initDraftOperations() {
    // Draft selection functionality
    const draftSelect = document.getElementById('draft_select');
    if (draftSelect) {
        draftSelect.addEventListener('change', function() {
            const draftId = this.value;
            if (!draftId) return;
            
            loadDraftIntoForm(draftId);
        });
        
        // Auto-load draft if specified in URL
        const urlParams = new URLSearchParams(window.location.search);
        const draftId = urlParams.get('draft_id');
        if (draftId) {
            // If draft is in select options, select it
            let draftExists = false;
            for (let i = 0; i < draftSelect.options.length; i++) {
                if (draftSelect.options[i].value === draftId) {
                    draftSelect.value = draftId;
                    draftExists = true;
                    break;
                }
            }
            
            // If draft is not in select options, add it
            if (!draftExists) {
                const option = document.createElement('option');
                option.value = draftId;
                option.text = `Draft (Loading...)`;
                draftSelect.appendChild(option);
                draftSelect.value = draftId;
            }
            
            // Load the draft
            loadDraftIntoForm(draftId);
        }
    }
    
    // Save draft button
    const saveDraftBtn = document.getElementById('save-draft-btn');
    if (saveDraftBtn) {
        saveDraftBtn.addEventListener('click', function() {
            saveDraft();
        });
    }
}

function loadTemplateIntoForm(templateId, showNotification = true) {
    // Show loading indicator
    const bodyInput = document.getElementById('body-input');
    const htmlEditorFrame = document.getElementById('html-editor-frame');
    if (bodyInput) bodyInput.placeholder = 'Loading template...';
    
    // Fetch template data
    fetch(`/templates/${templateId}`)
        .then(response => response.json())
        .then(data => {
            // Populate form fields
            document.getElementById('subject').value = data.subject || '';
            
            // Process the body content
            let bodyContent = data.body || '';
            if (bodyInput) bodyInput.value = bodyContent;
            
            // Update iframe if tab is active
            if (htmlEditorFrame && document.getElementById('visual-body').classList.contains('show')) {
                try {
                    // Initialize iframe with template content
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
                        <body contenteditable="true">${extractBodyContent(bodyContent)}</body>
                        </html>
                    `);
                    iframeDoc.close();
                    
                    // Add event listener to sync changes
                    iframeDoc.body.addEventListener('input', function() {
                        bodyInput.value = iframeDoc.body.innerHTML;
                    });
                } catch (e) {
                    console.error('Error updating iframe:', e);
                }
            }
            
        })
        .catch(error => {
            console.error('Error loading template:', error);
            if (showNotification) {
            }
            if (bodyInput) bodyInput.placeholder = 'Enter your email content here...';
        });
}

function loadDraftIntoForm(draftId) {
    // Fetch draft data
    fetch(`/draft/${draftId}`)
        .then(response => response.json())
        .then(data => {
            // Populate form fields
            document.getElementById('mail_from').value = data.mail_from || '';
            document.getElementById('mail_to').value = data.mail_to || '';
            document.getElementById('mail_envelope').value = data.mail_envelope || '';
            document.getElementById('subject').value = data.subject || '';
            document.getElementById('body-input').value = data.body || '';
            document.getElementById('spoof_domain').value = data.spoof_domain || '';
            document.getElementById('bcc').value = data.bcc || '';
            document.getElementById('draft_id').value = draftId;
            
            // Update visual editor if available
            const htmlEditor = document.getElementById('html-editor');
            if (htmlEditor) {
                htmlEditor.innerHTML = data.body || '';
            }
            
            // Update draft dropdown option if needed
            const draftSelect = document.getElementById('draft_select');
            if (draftSelect) {
                for (let i = 0; i < draftSelect.options.length; i++) {
                    if (draftSelect.options[i].value === draftId && draftSelect.options[i].text.includes('Loading')) {
                        draftSelect.options[i].text = `Draft (${new Date().toLocaleString()})`;
                        break;
                    }
                }
            }
            
        })
        .catch(error => {
            console.error('Error loading draft:', error);
            showNotification('Error', 'Failed to load draft', 'error');
        });
}

function saveDraft() {
    const form = document.getElementById('email-form');
    if (!form) return;
    
    const formData = new FormData(form);
    
    fetch('/drafts', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Success', 'Draft saved successfully', 'success');
            
            // Update the draft ID
            document.getElementById('draft_id').value = data.draft_id;
            
            // Add the new draft to the dropdown if it's not already there
            const draftSelect = document.getElementById('draft_select');
            if (draftSelect) {
                let draftExists = false;
                for (let i = 0; i < draftSelect.options.length; i++) {
                    if (draftSelect.options[i].value === data.draft_id) {
                        draftExists = true;
                        break;
                    }
                }
                
                if (!draftExists) {
                    const option = document.createElement('option');
                    option.value = data.draft_id;
                    option.text = `Draft (Just now)`;
                    draftSelect.appendChild(option);
                    draftSelect.value = data.draft_id;
                }
            }
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    })
    .catch(error => {
        console.error('Error saving draft:', error);
        showNotification('Error', 'Failed to save draft', 'error');
    });
}

function previewTemplate(templateId) {
    const previewCard = document.getElementById('template-preview-card');
    if (!previewCard) return;
    
    // Show loading state
    document.getElementById('preview-template-name').textContent = 'Loading...';
    document.getElementById('preview-subject').textContent = '';
    const previewFrame = document.getElementById('preview-body-frame');
    
    // Show loading indicator in iframe
    if (previewFrame) {
        const frameDoc = previewFrame.contentDocument || previewFrame.contentWindow.document;
        if (frameDoc) {
            frameDoc.open();
            frameDoc.write('<html><body style="display:flex;justify-content:center;align-items:center;height:100%;margin:0;font-family:Arial,sans-serif;"><div class="spinner-border text-primary" role="status" style="width:3rem;height:3rem;border-width:0.25em;"></div></body></html>');
            frameDoc.close();
        }
    }
    
    previewCard.classList.remove('d-none');
    
    // Fetch template data
    fetch(`/templates/${templateId}`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('preview-template-name').textContent = data.name;
            document.getElementById('preview-subject').textContent = data.subject || 'No subject';
            
            // Process the content
            let htmlContent = '';
            if (data.html_body) {
                htmlContent = data.html_body;
            } else {
                htmlContent = data.body || 'No body content';
            }
            
            // Use iframe to safely render HTML content
            if (previewFrame) {
                const frameDoc = previewFrame.contentDocument || previewFrame.contentWindow.document;
                if (frameDoc) {
                    frameDoc.open();
                    frameDoc.write(`
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <style>
                                body {
                                    font-family: Arial, sans-serif;
                                    padding: 0;
                                    margin: 0;
                                    line-height: 1.6;
                                }
                                img { max-width: 100%; height: auto; }
                                table { max-width: 100%; }
                                div.container { padding: 0; }
                            </style>
                        </head>
                        <body>${extractBodyContent(htmlContent)}</body>
                        </html>
                    `);
                    frameDoc.close();
                }
            }
            
            // Set up the "Use This Template" button
            const useTemplateBtn = document.getElementById('use-template-btn');
            if (useTemplateBtn) {
                useTemplateBtn.onclick = function() {
                    window.location.href = `/?template_id=${templateId}`;
                };
            }
        })
        .catch(error => {
            console.error('Error fetching template:', error);
            document.getElementById('preview-template-name').textContent = 'Error';
            
            if (previewFrame) {
                const frameDoc = previewFrame.contentDocument || previewFrame.contentWindow.document;
                if (frameDoc) {
                    frameDoc.open();
                    frameDoc.write('<html><body style="padding:15px;font-family:Arial,sans-serif;"><div style="color:#721c24;background-color:#f8d7da;padding:15px;border-radius:4px;border:1px solid #f5c6cb;">Error loading template</div></body></html>');
                    frameDoc.close();
                }
            }
        });
}

// Helper function to extract body content from HTML
function extractBodyContent(htmlString) {
    try {
        // Create a temporary element to parse the HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = htmlString;
        
        // Extract body content if available
        const bodyElement = tempDiv.querySelector('body');
        let content;
        
        if (bodyElement) {
            content = bodyElement.innerHTML;
        } else {
            // If no body tag found, return the original content
            content = htmlString;
        }
        
        // Sanitize the content to prevent layout breaking
        return sanitizeHtmlForPreview(content);
    } catch (error) {
        console.error('Error extracting body content:', error);
        return sanitizeHtmlForPreview(htmlString);
    }
}

function loadTemplateForEditing(templateId) {
    const editForm = document.getElementById('edit-template-form');
    if (!editForm) return;
    
    // Update form action
    editForm.action = `/templates/${templateId}/edit`;
    
    // Fetch template data
    fetch(`/templates/${templateId}`)
        .then(response => response.json())
        .then(data => {
            // Populate form fields
            document.getElementById('edit_template_name').value = data.name || '';
            document.getElementById('edit_template_description').value = data.description || '';
            document.getElementById('edit_subject').value = data.subject || '';
            document.getElementById('edit-template-body-input').value = data.body || '';
            
            // Also update the visual editor if present
            const editTemplateHtmlEditor = document.getElementById('edit-template-html-editor');
            if (editTemplateHtmlEditor) {
                editTemplateHtmlEditor.innerHTML = data.body || '';
            }
            
            // Show modal
            const editModal = new bootstrap.Modal(document.getElementById('editTemplateModal'));
            editModal.show();
        })
        .catch(error => {
            console.error('Error fetching template:', error);
            showNotification('Error', 'Failed to load template for editing', 'error');
        });
}

function confirmDeleteTemplate(templateId, templateName) {
    const deleteName = document.getElementById('delete-template-name');
    if (!deleteName) return;
    
    // Update modal content
    deleteName.textContent = templateName;
    
    // Set up confirm button action
    const confirmBtn = document.getElementById('confirm-delete-template');
    if (confirmBtn) {
        confirmBtn.onclick = function() {
            // Send delete request
            fetch(`/templates/${templateId}/delete`, {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Hide modal
                    const deleteModal = bootstrap.Modal.getInstance(document.getElementById('deleteTemplateModal'));
                    deleteModal.hide();
                    
                    // Show success notification
                    showNotification('Success', 'Template deleted successfully', 'success');
                    
                    // Reload page after short delay
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
            })
            .catch(error => {
                console.error('Error deleting template:', error);
                showNotification('Error', 'Failed to delete template', 'error');
            });
        };
    }
    
    // Show modal
    const deleteModal = new bootstrap.Modal(document.getElementById('deleteTemplateModal'));
    deleteModal.show();
}
