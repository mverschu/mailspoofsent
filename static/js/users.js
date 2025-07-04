document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('upload-form');
    const addUserForm = document.getElementById('add-user-form');
    const userList = document.getElementById('user-list');

    function fetchUsers() {
        fetch('/api/users')
            .then(response => response.json())
            .then(users => {
                userList.innerHTML = '';
                users.forEach(user => {
                    const li = document.createElement('li');
                    li.className = 'list-group-item d-flex justify-content-between align-items-center';
                    li.textContent = user;

                    const deleteButton = document.createElement('button');
                    deleteButton.className = 'btn btn-danger btn-sm';
                    deleteButton.innerHTML = '<i class="fas fa-trash"></i>';
                    deleteButton.addEventListener('click', function() {
                        deleteUser(user);
                    });

                    li.appendChild(deleteButton);
                    userList.appendChild(li);
                });
            });
    }

    function deleteUser(email) {
        fetch(`/api/users/${email}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Success', 'User deleted successfully!', 'success');
                fetchUsers();
            } else {
                showNotification('Error', 'Failed to delete user: ' + data.error, 'danger');
            }
        });
    }

    uploadForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const formData = new FormData(uploadForm);
        fetch('/api/users',
            {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    fetchUsers();
                } else {
                    alert('Error uploading file: ' + data.error);
                }
            });
    });

    addUserForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const emailInput = document.getElementById('email-input');
        const email = emailInput.value.trim();
        if (email) {
            fetch('/api/users',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email: email })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        fetchUsers();
                        emailInput.value = '';
                    } else {
                        alert('Error adding user: ' + data.error);
                    }
                });
        }
    });

    fetchUsers();
});
