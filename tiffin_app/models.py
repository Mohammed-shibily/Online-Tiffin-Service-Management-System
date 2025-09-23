from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('customer', 'Customer'),
        ('tiffin_provider', 'Tiffin Provider'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='customer')
    # You can add more fields here like phone_number, address, profile_picture etc.
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.username

# In tiffin_app/models.py, continue from CustomUser
# ... (CustomUser definition) ...

class TiffinPlan(models.Model):
    FREQUENCY_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    is_active = models.BooleanField(default=True) # To activate/deactivate plans

    # Optional: Link to the TiffinProvider if you want to differentiate
    # provider = models.ForeignKey(CustomUser, on_delete=models.CASCADE,
    #                              limit_choices_to={'user_type': 'tiffin_provider'},
    #                              related_name='provided_plans', blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
    
    # ... (TiffinPlan definition) ...

class MenuItem(models.Model):
    DIETARY_CHOICES = (
        ('veg', 'Vegetarian'),
        ('non_veg', 'Non-Vegetarian'),
        ('vegan', 'Vegan'),
        ('gluten_free', 'Gluten-Free'),
    )
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    dietary_info = models.CharField(max_length=20, choices=DIETARY_CHOICES, default='veg')
    image = models.ImageField(upload_to='menu_items/', blank=True, null=True) # Requires pillow: pip install Pillow

    def __str__(self):
        return self.name
    
    # ... (MenuItem definition) ...

class TiffinPlanMenuItem(models.Model):
    tiffin_plan = models.ForeignKey(TiffinPlan, on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('tiffin_plan', 'menu_item')

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name} in {self.tiffin_plan.name}"