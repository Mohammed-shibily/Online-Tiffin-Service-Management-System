# In tiffin_app/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, TiffinPlan, MenuItem, TiffinPlanMenuItem # This line
from .forms import CustomUserCreationForm, CustomUserChangeForm

# ... (rest of the admin.py code) ...
# Register CustomUser with your custom admin form
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ['username', 'email', 'user_type', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('user_type', 'phone_number', 'address')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('user_type', 'phone_number', 'address')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)


# Register your tiffin models
admin.site.register(TiffinPlan)
admin.site.register(MenuItem)
admin.site.register(TiffinPlanMenuItem)
