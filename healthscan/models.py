from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    GOAL_CHOICES = [
        ('GENERAL', 'General Health'),
        ('WEIGHT_LOSS', 'Weight Loss'),
        ('MUSCLE_GAIN', 'Muscle Gain'),
        ('DIABETES', 'Diabetes-Friendly'),
    ]
    LANG_CHOICES = [
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('mr', 'Marathi'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    health_goal = models.CharField(max_length=20, choices=GOAL_CHOICES, default='GENERAL')
    preferred_language = models.CharField(max_length=5, choices=LANG_CHOICES, default='en')
    onboarding_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Ensure profile exists before saving (useful for existing users or tests)
    if not hasattr(instance, 'profile'):
        UserProfile.objects.create(user=instance)
    instance.profile.save()

class ProductScanHistory(models.Model):
    RISK_CHOICES = [
        ('HEALTHY', 'Healthy'),
        ('MODERATE', 'Moderate'),
        ('UNHEALTHY', 'Unhealthy'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scan_history')
    barcode = models.CharField(max_length=50)
    product_name = models.CharField(max_length=255, blank=True, null=True)
    
    # Store minimal AI evaluation metrics for log reports
    health_score = models.FloatField(blank=True, null=True)  # 0 to 10
    risk_level = models.CharField(max_length=15, choices=RISK_CHOICES, default='MODERATE')
    harmful_ingredients = models.JSONField(default=list, blank=True)
    applied_goal = models.CharField(max_length=50, blank=True, null=True)
    
    scanned_at = models.DateTimeField(auto_now_add=True) # Purchase date

    class Meta:
        ordering = ['-scanned_at']

    def __str__(self):
        return f"{self.product_name or 'Unknown'} ({self.barcode}) logged by {self.user.username}"

class SavedProducts(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_products')
    barcode = models.CharField(max_length=50)
    product_name = models.CharField(max_length=255, blank=True, null=True)
    brand = models.CharField(max_length=255, blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    health_score = models.FloatField(blank=True, null=True)
    risk_level = models.CharField(max_length=15, blank=True, null=True)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'barcode')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.product_name or self.barcode} saved by {self.user.username}"
