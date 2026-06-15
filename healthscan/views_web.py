from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.contrib import messages

from .models import UserProfile, ProductScanHistory, SavedProducts
from .services import analyze_product_with_gemini

def landing_view(request):
    """
    Renders landing page. If user is authenticated, we show stats & navigation.
    If not, we show registration options.
    """
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        recent_scans = ProductScanHistory.objects.filter(user=request.user)[:3]
        saved_count = SavedProducts.objects.filter(user=request.user).count()
        scan_count = ProductScanHistory.objects.filter(user=request.user).count()
        context = {
            'profile': profile,
            'recent_scans': recent_scans,
            'saved_count': saved_count,
            'scan_count': scan_count,
        }
        return render(request, 'healthscan/landing.html', context)
    return render(request, 'healthscan/landing.html')

@login_required
def scanner_view(request):
    """
    Renders the barcode scanner page.
    """
    return render(request, 'healthscan/scanner.html')

@login_required
def results_view(request, barcode):
    """
    Renders the analysis report/dashboard for a specific product scan.
    Loaded transiently from session cache.
    """
    # Retrieve transient data from session cache
    scan_data = request.session.get(f'transient_scan_{barcode}')

    if not scan_data:
        messages.error(request, f"No scan report found for barcode {barcode}. Please scan the product first.")
        return redirect('scanner')

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Reactive synchronization: Re-run analysis if the user's preferred language or goal has changed
    if scan_data.get('applied_language') != profile.preferred_language or scan_data.get('applied_goal') != profile.health_goal:
        product_data = {
            'product_name': scan_data.get('product_name'),
            'brand': scan_data.get('brand'),
            'image_url': scan_data.get('image_url'),
            'ingredients_text': scan_data.get('ingredients_text'),
            'nutrition_facts': scan_data.get('nutrition_facts')
        }
        analysis = analyze_product_with_gemini(product_data, profile.health_goal, profile.preferred_language)
        
        # Update session data
        scan_data['applied_goal'] = profile.health_goal
        scan_data['applied_language'] = profile.preferred_language
        scan_data['health_score'] = analysis.get('health_score')
        
        classification = str(analysis.get('classification', 'MODERATE')).upper()
        if 'UNHEALTHY' in classification or 'अस्वस्थ' in classification or 'अनिरोगी' in classification:
            risk_level = 'UNHEALTHY'
        elif 'HEALTHY' in classification or 'स्वस्थ' in classification or 'निरोगी' in classification:
            risk_level = 'HEALTHY'
        else:
            risk_level = 'MODERATE'
            
        scan_data['risk_level'] = risk_level
        scan_data['harmful_ingredients'] = analysis.get('harmful_ingredients', [])
        scan_data['risk_explanation'] = analysis.get('risk_explanation')
        scan_data['consumption_frequency'] = analysis.get('consumption_frequency')
        scan_data['alternatives'] = analysis.get('alternatives', [])
        request.session[f'transient_scan_{barcode}'] = scan_data

    # Check if this product is already marked as bought
    is_logged = ProductScanHistory.objects.filter(user=request.user, barcode=barcode).exists()
    is_saved = SavedProducts.objects.filter(user=request.user, barcode=barcode).exists()

    context = {
        'scan': scan_data,
        'is_logged': is_logged,
        'is_saved': is_saved,
    }
    return render(request, 'healthscan/results.html', context)


@login_required
def settings_view(request):
    """
    Renders user profile settings and the Baymax Health Report dashboard.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    # Fetch purchase history
    purchase_history = ProductScanHistory.objects.filter(user=request.user)
    
    # Calculate statistics
    total_products = purchase_history.count()
    
    # Average Health Score
    from django.db.models import Avg
    avg_score = purchase_history.aggregate(Avg('health_score'))['health_score__avg'] or 0.0
    
    # Healthy vs Unhealthy consumption breakdown
    healthy_count = purchase_history.filter(risk_level='HEALTHY').count()
    moderate_count = purchase_history.filter(risk_level='MODERATE').count()
    unhealthy_count = purchase_history.filter(risk_level='UNHEALTHY').count()
    
    # Most Frequently Consumed Harmful Ingredients
    harmful_counts = {}
    for item in purchase_history:
        if isinstance(item.harmful_ingredients, list):
            for ing in item.harmful_ingredients:
                harmful_counts[ing] = harmful_counts.get(ing, 0) + 1
    
    # Sort harmful ingredients by frequency
    sorted_harmful = sorted(harmful_counts.items(), key=lambda x: x[1], reverse=True)
    top_harmful = [{'name': name, 'count': count} for name, count in sorted_harmful[:5]]
    
    # Generate eating pattern analysis and recommendations using Gemini/Mock service
    from .services import generate_diet_report_with_gemini
    diet_report = generate_diet_report_with_gemini(purchase_history, profile.health_goal, profile.preferred_language)
    
    context = {
        'profile': profile,
        'goals': UserProfile.GOAL_CHOICES,
        'languages': UserProfile.LANG_CHOICES,
        
        # Health Report Dashboard data
        'total_products': total_products,
        'avg_score': round(avg_score, 1),
        'healthy_count': healthy_count,
        'moderate_count': moderate_count,
        'unhealthy_count': unhealthy_count,
        'top_harmful': top_harmful,
        'diet_analysis': diet_report.get('analysis'),
        'diet_recommendations': diet_report.get('recommendations', []),
    }
    return render(request, 'healthscan/settings.html', context)

class RegisterView(CreateView):
    """
    Web view for registering a new user.
    """
    form_class = UserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('landing')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object) # Log user in after successful registration
        messages.success(self.request, "Account created successfully! Welcome to Baymax HealthScan.")
        return response

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('landing')
        return super().dispatch(request, *args, **kwargs)
