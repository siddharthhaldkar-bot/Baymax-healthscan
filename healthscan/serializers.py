from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, ProductScanHistory, SavedProducts

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    goal_display = serializers.CharField(source='get_health_goal_display', read_only=True)
    language_display = serializers.CharField(source='get_preferred_language_display', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'health_goal', 'goal_display', 'preferred_language', 'language_display', 'onboarding_completed']

class ProductScanHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductScanHistory
        fields = [
            'id', 'barcode', 'product_name', 'health_score', 
            'risk_level', 'harmful_ingredients', 'applied_goal', 'scanned_at'
        ]
        read_only_fields = ['id', 'scanned_at']

class SavedProductsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedProducts
        fields = ['id', 'barcode', 'product_name', 'brand', 'image_url', 'health_score', 'risk_level', 'saved_at']
        read_only_fields = ['id', 'saved_at']

    def validate(self, attrs):
        user = self.context['request'].user
        barcode = attrs.get('barcode')
        if SavedProducts.objects.filter(user=user, barcode=barcode).exists():
            raise serializers.ValidationError("This product is already saved.")
        return attrs
