from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch
import json

from .models import UserProfile, ProductScanHistory, SavedProducts
from .services import fetch_open_food_facts_data, analyze_product_with_gemini, generate_mock_analysis

class UserProfileSignalsTest(TestCase):
    def test_profile_created_automatically(self):
        """
        Verify that a UserProfile is created via signals whenever a User is created.
        """
        user = User.objects.create_user(username='testuser', password='password123')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.health_goal, 'GENERAL')
        self.assertEqual(user.profile.preferred_language, 'en')

class ServicesTest(TestCase):
    @patch('healthscan.services.requests.get')
    def test_fetch_open_food_facts_success(self, mock_get):
        """
        Test successful Open Food Facts product retrieval.
        """
        mock_response = {
            'status': 1,
            'product': {
                'product_name': 'Mock Chocolate',
                'brands': 'Mock Brand',
                'image_front_url': 'http://example.com/image.jpg',
                'ingredients_text': 'sugar, cocoa butter, milk',
                'nutriments': {
                    'energy-kcal_100g': 530,
                    'fat_100g': 30,
                    'saturated-fat_100g': 18,
                    'carbohydrates_100g': 58,
                    'sugars_100g': 50,
                    'proteins_100g': 6,
                    'salt_100g': 0.2,
                    'fiber_100g': 3
                }
            }
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        data = fetch_open_food_facts_data('1234567890123')
        self.assertIsNotNone(data)
        self.assertEqual(data['product_name'], 'Mock Chocolate')
        self.assertEqual(data['brand'], 'Mock Brand')
        self.assertEqual(data['nutrition_facts']['energy_kcal'], 530)
        self.assertEqual(data['nutrition_facts']['sugars'], 50)

    @patch('healthscan.services.requests.get')
    def test_fetch_open_food_facts_not_found(self, mock_get):
        """
        Test Open Food Facts handles product not found (status 0).
        """
        mock_response = {'status': 0}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        data = fetch_open_food_facts_data('0000000000000')
        self.assertIsNull = data
        self.assertIsNone(data)

    def test_mock_analysis_generation(self):
        """
        Test fallback mock analysis logic works for different languages and goals.
        """
        product_data = {
            'product_name': 'Sweet Cookies',
            'brand': 'Baker Co',
            'ingredients_text': 'sugar, flour, butter, processing chemicals',
            'nutrition_facts': {
                'energy_kcal': 400,
                'fat': 22,
                'sugars': 25,
                'proteins': 4
            }
        }
        # Test WEIGHT_LOSS goal in English
        analysis_en = generate_mock_analysis(product_data, 'WEIGHT_LOSS', 'en')
        explanation = analysis_en['risk_explanation'].lower()
        self.assertTrue('sugar' in explanation or 'calorie' in explanation)
        self.assertLess(analysis_en['health_score'], 6.0)

        # Test DIABETES goal in Hindi
        analysis_hi = generate_mock_analysis(product_data, 'DIABETES', 'hi')
        self.assertIn('चीनी', analysis_hi['risk_explanation']) # Hindi word for sugar

class APIEndpointsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='apiuser', password='password123')
        self.profile = self.user.profile

    def test_endpoints_require_authentication(self):
        """
        Ensure endpoints return 403 Forbidden for unauthenticated users.
        """
        response = self.client.get(reverse('api-profile'))
        self.assertEqual(response.status_code, 403)
        
        response = self.client.get(reverse('api-history'))
        self.assertEqual(response.status_code, 403)

    def test_profile_get_and_update(self):
        """
        Test retrieving and updating UserProfile settings.
        """
        self.client.login(username='apiuser', password='password123')
        
        # GET profile
        response = self.client.get(reverse('api-profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['health_goal'], 'GENERAL')

        # PUT profile update
        response = self.client.put(
            reverse('api-profile'),
            data=json.dumps({'health_goal': 'WEIGHT_LOSS', 'preferred_language': 'hi'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['health_goal'], 'WEIGHT_LOSS')
        self.assertEqual(response.json()['preferred_language'], 'hi')
        
        # Refresh from db
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.health_goal, 'WEIGHT_LOSS')

    @patch('healthscan.views_api.fetch_open_food_facts_data')
    @patch('healthscan.views_api.analyze_product_with_gemini')
    def test_scan_does_not_create_history_until_purchase_logged(self, mock_analyze, mock_fetch):
        """
        Test barcode scanning API does not write to DB, and logging a purchase does.
        """
        self.client.login(username='apiuser', password='password123')
        
        mock_fetch.return_value = {
            'product_name': 'Super Juice',
            'brand': 'Fruit Inc',
            'image_url': 'http://juice.com/img.png',
            'ingredients_text': 'water, apples, synthetic flavor',
            'nutrition_facts': {'energy_kcal': 45, 'sugars': 10, 'fat': 0, 'proteins': 0}
        }
        mock_analyze.return_value = {
            'health_score': 6.0,
            'classification': 'Moderate',
            'harmful_ingredients': ['Synthetic flavor'],
            'risk_explanation': 'Moderate due to synthetic flavoring.',
            'consumption_frequency': 'Occasionally',
            'alternatives': ['Fresh whole apples']
        }

        # 1. Post to scan API (transient analysis)
        response = self.client.post(
            reverse('api-scan'),
            data=json.dumps({'barcode': '9876543210987'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['product_name'], 'Super Juice')
        
        # Verify NOT saved in database yet
        self.assertFalse(ProductScanHistory.objects.filter(user=self.user, barcode='9876543210987').exists())
        
        # 2. Log purchase via history API
        response = self.client.post(
            reverse('api-history'),
            data=json.dumps({'barcode': '9876543210987'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['product_name'], 'Super Juice')
        
        # Verify now saved in database
        self.assertTrue(ProductScanHistory.objects.filter(user=self.user, barcode='9876543210987').exists())
