// Plan configurations
const plans = {
    'basic-monthly': {
        name: 'Basic Monthly Plan',
        duration: '30 days',
        meals: '1 meal/day',
        price: 299900,
        priceDisplay: '₹2,999'
    },
    'standard-monthly': {
        name: 'Standard Monthly Plan',
        duration: '30 days',
        meals: '2 meals/day',
        price: 499900,
        priceDisplay: '₹4,999'
    },
    'premium-monthly': {
        name: 'Premium Monthly Plan',
        duration: '30 days',
        meals: '3 meals/day',
        price: 699900,
        priceDisplay: '₹6,999'
    },
    'basic-weekly': {
        name: 'Basic Weekly Plan',
        duration: '7 days',
        meals: '1 meal/day',
        price: 79900,
        priceDisplay: '₹799'
    },
    'standard-weekly': {
        name: 'Standard Weekly Plan',
        duration: '7 days',
        meals: '2 meals/day',
        price: 129900,
        priceDisplay: '₹1,299'
    },
    'premium-weekly': {
        name: 'Premium Weekly Plan',
        duration: '7 days',
        meals: '3 meals/day',
        price: 179900,
        priceDisplay: '₹1,799'
    }
};

// Get plan from URL
const urlParams = new URLSearchParams(window.location.search);
const planId = urlParams.get('plan');
const currentPlan = plans[planId];

if (!currentPlan) {
    alert('Invalid plan selected');
    window.location.href = '/plans';
}

// Update UI
document.getElementById('plan-name').textContent = currentPlan.name;
document.getElementById('plan-duration').textContent = currentPlan.duration;
document.getElementById('plan-meals').textContent = currentPlan.meals;
document.getElementById('plan-price').textContent = currentPlan.priceDisplay;

// Initialize Stripe
let stripe;
let elements;
let cardElement;

async function initializeStripe() {
    try {
        const response = await fetch('/get_stripe_config');
        const { publishableKey } = await response.json();
        
        stripe = Stripe(publishableKey);
        elements = stripe.elements();
        
        cardElement = elements.create('card', {
            style: {
                base: {
                    fontSize: '16px',
                    color: '#32325d',
                    fontFamily: '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif',
                    '::placeholder': {
                        color: '#aab7c4'
                    }
                },
                invalid: {
                    color: '#e74c3c',
                    iconColor: '#e74c3c'
                }
            }
        });
        
        cardElement.mount('#card-element');
        
        cardElement.on('change', function(event) {
            const displayError = document.getElementById('card-errors');
            if (event.error) {
                displayError.textContent = event.error.message;
            } else {
                displayError.textContent = '';
            }
        });
        
    } catch (error) {
        console.error('Error initializing Stripe:', error);
        alert('Failed to load payment system. Please refresh the page.');
    }
}

// Handle form submission
const form = document.getElementById('payment-form');
const submitButton = document.getElementById('submit-button');

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    
    submitButton.disabled = true;
    submitButton.classList.add('loading');
    
    try {
        const name = document.getElementById('name').value;
        const email = document.getElementById('email').value;
        const phone = document.getElementById('phone').value;
        
        // Create payment intent
        const paymentIntentResponse = await fetch('/create_payment_intent', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: planId,
                amount: currentPlan.price,
                currency: 'INR',
                description: currentPlan.name,
                customer: {
                    name: name,
                    email: email,
                    phone: phone
                }
            })
        });
        
        if (!paymentIntentResponse.ok) {
            const errorData = await paymentIntentResponse.json();
            throw new Error(errorData.error || 'Failed to create payment intent');
        }
        
        const { clientSecret } = await paymentIntentResponse.json();
        
        // Confirm payment
        const { error, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
            payment_method: {
                card: cardElement,
                billing_details: {
                    name: name,
                    email: email,
                    phone: phone
                }
            }
        });
        
        if (error) {
            throw new Error(error.message);
        } else if (paymentIntent.status === 'succeeded') {
            // Confirm with backend
            const confirmResponse = await fetch('/confirm_payment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    payment_intent_id: paymentIntent.id
                })
            });
            
            const confirmData = await confirmResponse.json();
            
            if (confirmData.success) {
                window.location.href = `/payment_success?plan=${planId}&amount=${currentPlan.priceDisplay}`;
            } else {
                throw new Error('Payment confirmation failed');
            }
        }
        
    } catch (error) {
        console.error('Payment error:', error);
        document.getElementById('card-errors').textContent = error.message;
        submitButton.disabled = false;
        submitButton.classList.remove('loading');
    }
});

// Initialize
initializeStripe();