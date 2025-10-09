// Complaint Form Modal
function openComplaintForm() {
    document.getElementById('complaintModal').classList.add('active');
}

function closeComplaintForm() {
    document.getElementById('complaintModal').classList.remove('active');
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('complaintModal');
    if (event.target === modal) {
        closeComplaintForm();
    }
}

// Handle complaint form submission
document.getElementById('complaintForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData);
    
    try {
        const response = await fetch('/submit_complaint', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('✓ Complaint submitted successfully! We will contact you soon.');
            closeComplaintForm();
            e.target.reset();
        } else {
            alert('❌ Error: ' + (result.error || 'Something went wrong'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('❌ Failed to submit complaint. Please try again.');
    }
});