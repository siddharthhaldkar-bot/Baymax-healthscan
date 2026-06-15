from django.urls import path
from django.contrib.auth import views as auth_views
from . import views_web, views_api

urlpatterns = [
    # Web View Routes
    path('', views_web.landing_view, name='landing'),
    path('scanner/', views_web.scanner_view, name='scanner'),
    path('results/<str:barcode>/', views_web.results_view, name='results'),
    path('settings/', views_web.settings_view, name='settings'),
    
    # Auth Web Routes
    path('register/', views_web.RegisterView.as_view(), name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='landing'), name='logout'),

    # REST API Routes
    path('api/scan/', views_api.ProductScanAPIView.as_view(), name='api-scan'),
    path('api/profile/', views_api.UserProfileAPIView.as_view(), name='api-profile'),
    path('api/history/', views_api.ProductScanHistoryListAPIView.as_view(), name='api-history'),
    path('api/saved/', views_api.SavedProductsAPIView.as_view(), name='api-saved'),
    path('api/saved/<str:barcode>/', views_api.SavedProductDetailAPIView.as_view(), name='api-saved-detail'),
]
