from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from .models import UserProfile, ProductScanHistory, SavedProducts
from .serializers import UserProfileSerializer, ProductScanHistorySerializer, SavedProductsSerializer
from .services import fetch_open_food_facts_data, analyze_product_with_gemini

class ProductScanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        barcode = request.data.get('barcode')
        if not barcode:
            return Response(
                {"error": "Barcode is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Normalize barcode by stripping spaces
        barcode = str(barcode).strip()
        
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        goal = profile.health_goal
        language = profile.preferred_language

        # 1. Check in-memory session cache first
        transient_data = request.session.get(f'transient_scan_{barcode}')
        if transient_data and transient_data.get('applied_goal') == goal and transient_data.get('applied_language') == language:
            return Response(transient_data, status=status.HTTP_200_OK)

        # 2. Fetch from Open Food Facts API
        product_data = fetch_open_food_facts_data(barcode)
        if not product_data:
            return Response(
                {"error": "Product not found in Open Food Facts database."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Analyze with Gemini API
        analysis = analyze_product_with_gemini(product_data, goal, language)

        # Normalize risk level to EN values for DB and style classes
        classification = str(analysis.get('classification', 'MODERATE')).upper()
        if 'UNHEALTHY' in classification or 'अस्वस्थ' in classification or 'अनिरोगी' in classification:
            risk_level = 'UNHEALTHY'
        elif 'HEALTHY' in classification or 'स्वस्थ' in classification or 'निरोगी' in classification:
            risk_level = 'HEALTHY'
        else:
            risk_level = 'MODERATE'

        # 4. Save to Session Cache (Not DB)
        transient_data = {
            'barcode': barcode,
            'product_name': product_data.get('product_name'),
            'brand': product_data.get('brand'),
            'image_url': product_data.get('image_url'),
            'ingredients_text': product_data.get('ingredients_text'),
            'nutrition_facts': product_data.get('nutrition_facts'),
            'health_score': analysis.get('health_score'),
            'risk_level': risk_level,
            'harmful_ingredients': analysis.get('harmful_ingredients', []),
            'risk_explanation': analysis.get('risk_explanation'),
            'consumption_frequency': analysis.get('consumption_frequency'),
            'alternatives': analysis.get('alternatives', []),
            'applied_goal': goal,
            'applied_language': language
        }
        request.session[f'transient_scan_{barcode}'] = transient_data
        
        return Response(transient_data, status=status.HTTP_200_OK)

class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProductScanHistoryListAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductScanHistorySerializer

    def get_queryset(self):
        return ProductScanHistory.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        barcode = request.data.get('barcode')
        if not barcode:
            return Response({"error": "Barcode is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Pull transient scan from session
        transient_data = request.session.get(f'transient_scan_{barcode}')
        if not transient_data:
            return Response(
                {"error": "No scan data found for this barcode in session. Please scan it first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already logged
        existing = ProductScanHistory.objects.filter(user=request.user, barcode=barcode).first()
        if existing:
            serializer = self.get_serializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Log purchase
        log_record = ProductScanHistory.objects.create(
            user=request.user,
            barcode=barcode,
            product_name=transient_data.get('product_name'),
            health_score=transient_data.get('health_score'),
            risk_level=transient_data.get('risk_level', 'MODERATE'),
            harmful_ingredients=transient_data.get('harmful_ingredients', []),
            applied_goal=transient_data.get('applied_goal')
        )
        serializer = self.get_serializer(log_record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class SavedProductsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        saved = SavedProducts.objects.filter(user=request.user)
        serializer = SavedProductsSerializer(saved, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        # Allow saving from scan history or arbitrary inputs
        serializer = SavedProductsSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SavedProductDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, barcode, *args, **kwargs):
        saved_item = get_object_or_404(SavedProducts, user=request.user, barcode=barcode)
        saved_item.delete()
        return Response({"message": "Product removed from saved list."}, status=status.HTTP_200_OK)
