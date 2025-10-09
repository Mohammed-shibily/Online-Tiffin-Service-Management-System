function showPlans(type) {
    // Hide all plan grids
    document.getElementById('monthly-plans').style.display = 'none';
    document.getElementById('weekly-plans').style.display = 'none';
    
    // Remove active class from all buttons
    document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected plan grid
    document.getElementById(type + '-plans').style.display = 'grid';
    
    // Add active class to clicked button
    event.target.classList.add('active');
}

function selectPlan(planId) {
    window.location.href = `/checkout?plan=${planId}`;
}