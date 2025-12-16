function predict() {
    var text = document.getElementById('text').value.trim();
    var predictionDiv = document.getElementById('prediction');
    var detailsDiv = document.getElementById('prediction-details');
    
    if (text === '') {
        predictionDiv.innerHTML = 'Please Enter Some Text';
        detailsDiv.style.display = 'none';
        return;
    }
    
    predictionDiv.innerHTML = 'Analyzing text...';
    detailsDiv.style.display = 'none';
    
    fetch('/predict/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            text: text
        })
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        if (data.error) {
            predictionDiv.innerHTML = 'Error: ' + data.error;
            detailsDiv.style.display = 'none';
            return;
        }
        
        // Display main prediction
        predictionDiv.innerHTML = `Predicted Category: <strong>${data.category}</strong>`;
        
        // Display detailed results
        document.getElementById('category-title').textContent = 
            `Category: ${data.category.charAt(0).toUpperCase() + data.category.slice(1)}`;
        document.getElementById('category-description').textContent = data.description;
        
        // Update confidence bar
        const confidenceFill = document.getElementById('confidence-fill');
        const confidenceText = document.getElementById('confidence-text');
        confidenceFill.style.width = '0%';
        
        setTimeout(() => {
            confidenceFill.style.width = data.confidence + '%';
            confidenceText.textContent = `Confidence: ${data.confidence}%`;
        }, 100);
        
        // Display probabilities
        const probabilitiesContainer = document.getElementById('probabilities-container');
        probabilitiesContainer.innerHTML = '';
        
        Object.entries(data.probabilities).forEach(([category, probability]) => {
            const probItem = document.createElement('div');
            probItem.className = 'probability-item';
            probItem.innerHTML = `
                <div class="probability-category">${category}</div>
                <div class="probability-value">${probability}%</div>
            `;
            probabilitiesContainer.appendChild(probItem);
        });
        
        // Show details with fade-in animation
        detailsDiv.style.display = 'block';
        detailsDiv.style.opacity = '0';
        detailsDiv.style.transform = 'translateY(-20px) scale(0.9)';
        detailsDiv.style.transition = 'opacity 0.5s ease, transform 0.5s ease';

        setTimeout(() => {
            detailsDiv.style.opacity = '1';
            detailsDiv.style.transform = 'translateY(0) scale(1)';
        }, 100);
        
    })
    .catch(function(error) {
        predictionDiv.innerHTML = 'Error: ' + error.message;
        detailsDiv.style.display = 'none';
    });
}

// Helper function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Add event listener for Enter key in textarea
document.getElementById('text').addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && e.ctrlKey) {
        predict();
    }
});
