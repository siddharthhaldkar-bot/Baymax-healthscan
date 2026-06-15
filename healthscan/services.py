import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def fetch_open_food_facts_data(barcode):
    """
    Fetch product information from Open Food Facts API v2.
    """
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    headers = {
        'User-Agent': 'BaymaxHealthScan/1.0 (django-backend)'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 1: # 1 means product found
                product = data.get('product', {})
                
                # Standardize nutriments dictionary
                nutriments = product.get('nutriments', {})
                standard_nutrients = {
                    'energy_kcal': nutriments.get('energy-kcal_100g', nutriments.get('energy_100g', 0)),
                    'fat': nutriments.get('fat_100g', 0),
                    'saturated_fat': nutriments.get('saturated-fat_100g', 0),
                    'carbohydrates': nutriments.get('carbohydrates_100g', 0),
                    'sugars': nutriments.get('sugars_100g', 0),
                    'proteins': nutriments.get('proteins_100g', 0),
                    'salt': nutriments.get('salt_100g', 0),
                    'sodium': nutriments.get('sodium_100g', 0),
                    'fiber': nutriments.get('fiber_100g', 0),
                }

                # Resolve brand
                brand = product.get('brands', '')
                if isinstance(brand, list):
                    brand = ', '.join(brand)

                return {
                    'barcode': barcode,
                    'product_name': product.get('product_name', 'Unknown Product'),
                    'brand': brand or 'Unknown Brand',
                    'image_url': product.get('image_front_url', product.get('image_url', '')),
                    'ingredients_text': product.get('ingredients_text', ''),
                    'nutrition_facts': standard_nutrients,
                    'nutriscore_grade': product.get('nutriscore_grade', '').upper()
                }
            else:
                logger.info(f"Product with barcode {barcode} not found in Open Food Facts.")
                return None
        else:
            logger.error(f"Open Food Facts API error: HTTP {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Connection error to Open Food Facts: {e}")
        return None

def analyze_product_with_gemini(product_data, health_goal, language):
    """
    Send ingredients and nutrition information to Gemini API.
    Provides a personalized evaluation based on the health goal
    and returns textual elements in the requested language (en, hi, mr).
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    
    # Resolve goal description
    goal_descriptions = {
        'GENERAL': 'General Health & Balanced Nutrition (focus on clean eating, low additives, high nutritional density).',
        'WEIGHT_LOSS': 'Weight Loss (focus on caloric density, high fiber, low sugars, portion control, healthy fats).',
        'MUSCLE_GAIN': 'Muscle Gain & Athletic Performance (focus on high protein, quality complex carbohydrates, amino acid profile).',
        'DIABETES': 'Diabetes-Friendly & Blood Sugar Management (focus on low glycemic index, zero/low added sugars, high fiber, complex carbohydrates).',
    }
    goal_text = goal_descriptions.get(health_goal, goal_descriptions['GENERAL'])

    # Build prompt
    prompt = f"""
    You are Baymax, a personal healthcare companion. Analyze the food product details below from the perspective of the user's specific health goal.
    
    User's Health Goal: {goal_text}
    
    Product details to analyze:
    - Product Name: {product_data.get('product_name', 'Unknown')}
    - Brand: {product_data.get('brand', 'Unknown')}
    - Ingredients: {product_data.get('ingredients_text', 'No ingredients list available')}
    - Nutrition facts per 100g:
      * Energy: {product_data.get('nutrition_facts', {}).get('energy_kcal', 0)} kcal
      * Fat: {product_data.get('nutrition_facts', {}).get('fat', 0)}g
      * Saturated Fat: {product_data.get('nutrition_facts', {}).get('saturated_fat', 0)}g
      * Carbohydrates: {product_data.get('nutrition_facts', {}).get('carbohydrates', 0)}g
      * Sugars: {product_data.get('nutrition_facts', {}).get('sugars', 0)}g
      * Proteins: {product_data.get('nutrition_facts', {}).get('proteins', 0)}g
      * Salt: {product_data.get('nutrition_facts', {}).get('salt', 0)}g
      * Fiber: {product_data.get('nutrition_facts', {}).get('fiber', 0)}g

    Provide the analysis strictly in JSON format. Do not include any markdown formatting or surrounding backticks. The JSON must match this structure:
    {{
      "health_score": <float between 0.0 and 10.0 representing suitability for user's goal>,
      "classification": "<'Healthy' or 'Moderate' or 'Unhealthy' based on score and goal suitability>",
      "harmful_ingredients": [<list of specific ingredients of concern for this health goal, using very simple common names, e.g. 'Added Sugar', 'High Salt', 'Palm Oil', 'Artificial Sweetener' instead of chemical terms>],
      "risk_explanation": "<A very simple, friendly, easy-to-read paragraph. Avoid scientific jargon, medical codes, or complex chemical terms. Explain the health impact in conversational terms that anyone can understand immediately. Write short, clear sentences. For example: 'This product has a lot of added sugar. Too much sugar gives you a quick energy burst but makes you feel tired later, which is not good for losing weight.' or 'This contains chemical preservatives that keep it fresh on shelves, but can cause stomach irritation.'>",
      "consumption_frequency": "<recommended consumption frequency in simple words, e.g., 'Good for daily eating', 'Eat occasionally', 'Eat rarely as a treat', 'Try to avoid'>",
      "alternatives": [<list of 3 simpler, healthier alternative food items suitable for this goal>]
    }}

    Language requirements:
    - Translate all strings (classification, risk_explanation, consumption_frequency, alternatives, harmful_ingredients) to the preferred language: {language}.
    - Preferred language code mapping:
      * 'en' -> Simple English
      * 'hi' -> Simple, everyday conversational Hindi (हिन्दी) that normal people speak. Avoid complex or highly formal Sanskritized Hindi. Use common colloquial terms and write English loanwords in Devanagari script (for example: use 'शुगर' for sugar, 'फैट' for fat, 'कैलोरी' for calories, 'केमिकल' for chemicals, 'मसल' for muscles, 'हार्ट' for heart, 'वजन कम करना' for weight loss) so anyone can read and understand it instantly.
      * 'mr' -> Simple, everyday conversational Marathi (मराठी).
    - Write in a friendly, reassuring, local conversational style (like Baymax).
    """

    # If API Key is missing, return a smart, mock response tailored to the goal/language
    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured. Returning mock analysis.")
        return generate_mock_analysis(product_data, health_goal, language)

    # Make direct API request to Gemini 1.5 Flash (or 3.5 Flash)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=12)
        if response.status_code == 200:
            result = response.json()
            # Extract content from response
            text_response = result['candidates'][0]['content']['parts'][0]['text'].strip()
            # Parse JSON
            analysis = json.loads(text_response)
            return analysis
        else:
            logger.error(f"Gemini API returned error: {response.status_code} - {response.text}")
            return generate_mock_analysis(product_data, health_goal, language)
    except Exception as e:
        logger.error(f"Failed to query or parse Gemini analysis: {e}")
        return generate_mock_analysis(product_data, health_goal, language)

def generate_mock_analysis(product_data, health_goal, language):
    """
    Generate a realistic, fallback analysis for development.
    Supports English, Hindi, and Marathi to ensure language switching is visible
    even without an active API key.
    """
    nut = product_data.get('nutrition_facts', {})
    sugars = nut.get('sugars', 0)
    fat = nut.get('fat', 0)
    proteins = nut.get('proteins', 0)
    energy = nut.get('energy_kcal', 0)

    # Basic scoring logic
    score = 7.5
    if sugars > 15 or fat > 20:
        score -= 3.0
    if health_goal == 'WEIGHT_LOSS' and energy > 250:
        score -= 2.0
    if health_goal == 'DIABETES' and sugars > 10:
        score -= 3.5
    if health_goal == 'MUSCLE_GAIN' and proteins > 10:
        score += 1.5
    
    score = max(0.5, min(10.0, score))
    
    classification = "Moderate"
    if score >= 7.0:
        classification = "Healthy"
    elif score < 4.0:
        classification = "Unhealthy"

    # Define multilingual values
    translations = {
        'en': {
            'Healthy': 'Healthy',
            'Moderate': 'Moderate',
            'Unhealthy': 'Unhealthy',
            'explanation_general': f"This product ({product_data.get('product_name')}) is moderately balanced. It has a reasonable amount of sugar ({sugars}g) and protein ({proteins}g). You can eat this in moderation.",
            'explanation_weight': f"This has a lot of calories ({energy} kcal). The fat ({fat}g) and sugar ({sugars}g) will make it harder to lose weight. Enjoy it only once in a while.",
            'explanation_muscle': f"This contains {proteins}g of protein to help build muscle, but check if the carbohydrate ratio fits your active lifestyle.",
            'explanation_diabetes': f"Caution: The sugar is quite high ({sugars}g). High sugar can spike your blood glucose quickly. It is better to avoid this product.",
            'freq_daily': 'Good for daily eating',
            'freq_occasional': 'Eat occasionally',
            'freq_rare': 'Eat rarely as a treat',
            'freq_avoid': 'Try to avoid',
            'harm_sugar': 'High Sugar',
            'harm_fat': 'High Fats',
            'harm_processing': 'Processed Additives',
            'alt_general': ['Fresh whole fruits', 'Oatmeal with nuts', 'Plain low-fat yogurt'],
            'alt_weight': ['Greek yogurt', 'Mixed raw berries', 'Green tea'],
            'alt_muscle': ['Whey protein shake', 'Boiled egg whites', 'Grilled chicken salad'],
            'alt_diabetes': ['Roasted almonds', 'Chia seed pudding', 'Avocado salad']
        },
        'hi': {
            'Healthy': 'स्वस्थ (Healthy)',
            'Moderate': 'मध्यम (Moderate)',
            'Unhealthy': 'अस्वस्थ (Unhealthy)',
            'explanation_general': f"यह उत्पाद ({product_data.get('product_name')}) ठीक है। इसमें मध्यम मात्रा में चीनी ({sugars} ग्राम) और प्रोटीन ({proteins} ग्राम) है। आप इसे कभी-कभार खा सकते हैं।",
            'explanation_weight': f"इसमें कैलोरी ({energy} kcal) और चीनी ({sugars} ग्राम) ज्यादा है। इसे अधिक खाने से वजन घटाने में मुश्किल होगी। इसे कभी-कभार ही खाएं।",
            'explanation_muscle': f"इसमें स्नायु (मसल) बनाने के लिए {proteins} ग्राम प्रोटीन है, लेकिन कार्बोहाइड्रेट की मात्रा भी देखें।",
            'explanation_diabetes': f"सावधानी: इसमें चीनी बहुत अधिक ({sugars} ग्राम) है। अधिक चीनी आपके ब्लड शुगर को तेजी से बढ़ा सकती है। इससे परहेज करना ही बेहतर है।",
            'freq_daily': 'रोज खाने के लिए अच्छा',
            'freq_occasional': 'कभी-कभार खाएं',
            'freq_rare': 'स्वाद के लिए कभी-कभार लें',
            'freq_avoid': 'परहेज करने की कोशिश करें',
            'harm_sugar': 'अधिक चीनी मात्रा',
            'harm_fat': 'अधिक वसा (Fats)',
            'harm_processing': 'प्रसंस्कृत सामग्री (Additives)',
            'alt_general': ['ताजे फल', 'मेवे के साथ ओट्स', 'सादा कम वसा वाला दही'],
            'alt_weight': ['ग्रीक दही', 'कच्चे जामुन', 'ग्रीन टी'],
            'alt_muscle': ['मट्ठा प्रोटीन (Whey)', 'उबले अंडे की सफेदी', 'ग्रिल्ड चिकन सलाद'],
            'alt_diabetes': ['भुने हुए बादाम', 'चिया बीज का हलवा', 'एवोकैडो सलाद']
        },
        'mr': {
            'Healthy': 'निरोगी (Healthy)',
            'Moderate': 'मध्यम (Moderate)',
            'Unhealthy': 'अनिरोगी (Unhealthy)',
            'explanation_general': f"हे उत्पादन ({product_data.get('product_name')}) सामान्यपणे संतुलित आहे. यात साखर ({sugars} ग्रॅम) आणि प्रोटीन ({proteins} ग्रॅम) आहे. मर्यादित प्रमाणात खाण्यास हरकत नाही.",
            'explanation_weight': f"यात कॅलरी ({energy} kcal) आणि साखर ({sugars} ग्रॅम) जास्त आहे. हे जास्त खाल्ल्यास वजन कमी करणे कठीण होईल. कधीतरीच खाणे योग्य ठरेल.",
            'explanation_muscle': f"यात स्नायूंच्या वाढीसाठी {proteins} ग्रॅम प्रोटीन आहे, पण कार्बोहायड्रेटचे प्रमाणही तपासा.",
            'explanation_diabetes': f"खबरदारी: यात साखरेचे प्रमाण खूप जास्त ({sugars} ग्रॅम) आहे. यामुळे रक्तातील साखर वेगाने वाढू शकते. हे खाणे टाळलेलेच बरे.",
            'freq_daily': 'दररोज खाण्यासाठी चांगले',
            'freq_occasional': 'कधीतरी खा',
            'freq_rare': 'कदाचितच खा',
            'freq_avoid': 'टाळण्याचा प्रयत्न करा',
            'harm_sugar': 'जास्त साखरेचे प्रमाण',
            'harm_fat': 'जास्त चरबी (Fats)',
            'harm_processing': 'प्रक्रिया केलेले घटक',
            'alt_general': ['ताजी फळे', 'सुक्या मेव्यांसह ओट्स', 'कमी चरबीचे साधे दही'],
            'alt_weight': ['ग्रीक दही', 'मिश्र बेरी', 'ग्रीन टी'],
            'alt_muscle': ['व्हे प्रोटीन शेक', 'उकडलेल्या अंड्यातील पांढरा भाग', 'ग्रील्ड चिकन सॅलड'],
            'alt_diabetes': ['भाजलेले बदाम', 'चिया बियांचे पुडिंग', 'अव्होकॅडो सॅलड']
        }
    }

    t = translations.get(language, translations['en'])
    
    # Map explanation based on goal
    explanation = t['explanation_general']
    if health_goal == 'WEIGHT_LOSS':
        explanation = t['explanation_weight']
    elif health_goal == 'MUSCLE_GAIN':
        explanation = t['explanation_muscle']
    elif health_goal == 'DIABETES':
        explanation = t['explanation_diabetes']

    # Map classification
    mapped_classification = t.get(classification, classification)

    # Harmful ingredients list
    harmful = []
    if sugars > 12:
        harmful.append(t['harm_sugar'])
    if fat > 15:
        harmful.append(t['harm_fat'])
    if 'processing' in product_data.get('ingredients_text', '').lower() or not product_data.get('ingredients_text'):
        harmful.append(t['harm_processing'])

    # Consumption Frequency
    frequency = t['freq_occasional']
    if score >= 7.0:
        frequency = t['freq_daily']
    elif score < 4.0:
        frequency = t['freq_avoid'] if health_goal in ['DIABETES', 'WEIGHT_LOSS'] else t['freq_rare']

    # Alternatives list
    alternatives = t['alt_general']
    if health_goal == 'WEIGHT_LOSS':
        alternatives = t['alt_weight']
    elif health_goal == 'MUSCLE_GAIN':
        alternatives = t['alt_muscle']
    elif health_goal == 'DIABETES':
        alternatives = t['alt_diabetes']

    return {
        "health_score": score,
        "classification": mapped_classification,
        "harmful_ingredients": harmful,
        "risk_explanation": explanation,
        "consumption_frequency": frequency,
        "alternatives": alternatives
    }

def generate_diet_report_with_gemini(purchase_history, health_goal, language):
    """
    Generate an overall eating pattern analysis and recommendations
    based on the user's logged purchases/consumed products.
    """
    total_products = len(purchase_history)
    if total_products == 0:
        if language == 'hi':
            return {
                'analysis': "अभी तक आपने कोई उत्पाद नहीं खरीदा है। अपनी ईटिंग हिस्ट्री रिकॉर्ड करने के लिए स्कैन करने के बाद उत्पाद को 'हाँ, मैंने खरीदा' मार्क करें!",
                'recommendations': ["स्कैन करना शुरू करें", "कम से कम 3-4 उत्पाद जोड़ें", "अपनी पसंद की भाषा और लक्ष्य चुनें"]
            }
        elif language == 'mr':
            return {
                'analysis': "अद्याप तुम्ही कोणतेही उत्पादन खरेदी केलेले नाही. तुमचा खाण्याचा इतिहास रेकॉर्ड करण्यासाठी उत्पादन स्कॅन करा आणि 'होय, मी खरेदी केले' वर क्लिक करा!",
                'recommendations': ["स्कॅन करण्यास सुरुवात करा", "किमान ३-४ उत्पादने जोडा", "आपले ध्येय आणि भाषा निवडा"]
            }
        else:
            return {
                'analysis': "No purchase history available yet. Please scan products and click 'Yes, I bought this' to log your purchases and get a personalized health report!",
                'recommendations': ["Start scanning products", "Log at least 3-4 items to generate insights", "Configure your goal and language preferences"]
            }

    # Aggregate information for prompt or local analysis
    avg_score = sum(item.health_score for item in purchase_history if item.health_score is not None) / total_products if total_products > 0 else 0.0
    
    # Extract all harmful ingredients
    harmful_counts = {}
    for item in purchase_history:
        ingredients = item.harmful_ingredients
        if isinstance(ingredients, list):
            for ing in ingredients:
                harmful_counts[ing] = harmful_counts.get(ing, 0) + 1
                
    # Sort harmful ingredients by frequency
    sorted_harmful = sorted(harmful_counts.items(), key=lambda x: x[1], reverse=True)
    top_harmful_str = ", ".join([f"{name} (consumed {count} times)" for name, count in sorted_harmful[:5]])

    # Build prompt for Gemini
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    
    goal_descriptions = {
        'GENERAL': 'General Health & Balanced Nutrition',
        'WEIGHT_LOSS': 'Weight Loss',
        'MUSCLE_GAIN': 'Muscle Gain',
        'DIABETES': 'Diabetes-Friendly Blood Sugar Management',
    }
    goal_text = goal_descriptions.get(health_goal, goal_descriptions['GENERAL'])

    products_summary = []
    for item in purchase_history[:10]: # Limit to last 10 products for prompt size
        products_summary.append(f"- {item.product_name or 'Product'} (Score: {item.health_score or 'N/A'}, Risk: {item.risk_level}, Harmful Ingredients: {', '.join(item.harmful_ingredients) if isinstance(item.harmful_ingredients, list) else ''})")
    products_text = "\n".join(products_summary)

    prompt = f"""
    You are Baymax, a personal healthcare companion. Analyze the user's recent dietary consumption logs and provide a personalized Health Report.
    
    User's Health Goal: {goal_text}
    
    Recent Consumed Products (Last 10 items):
    {products_text}
    
    Aggregate Statistics:
    - Total items logged: {total_products}
    - Average diet health score: {avg_score:.1f}/10
    - Top harmful ingredients consumed: {top_harmful_str}
    
    Provide the analysis strictly in JSON format. Do not include any markdown formatting or surrounding backticks. The JSON must match this structure:
    {{
      "analysis": "<A friendly, compassionate, easy-to-understand summary of their eating pattern based on their goal. Highlight any positive habits or warnings, keeping it conversational like Baymax. Explain the impact on their health without using complex medical jargon. Keep sentences short.>",
      "recommendations": [
        "<Actionable tip 1: simple, practical diet advice based on their goal and logs>",
        "<Actionable tip 2: another practical advice>",
        "<Actionable tip 3: another practical advice>"
      ]
    }}

    Language requirements:
    - Translate the entire analysis and all recommendations to the preferred language: {language}.
    - Preferred language code mapping:
      * 'en' -> Simple English
      * 'hi' -> Simple, colloquial conversational Hindi (हिन्दी) using common words (e.g. 'शुगर' for sugar, 'फैट' for fat, 'कैलोरी' for calories, 'केमिकल' for chemicals, 'वजन कम करना' for weight loss) so anyone can read and understand it instantly.
      * 'mr' -> Simple, everyday conversational Marathi (मराठी).
    - Write in a friendly, reassuring, local conversational style (like Baymax).
    """

    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured. Returning mock diet analysis.")
        return generate_mock_diet_report(avg_score, total_products, sorted_harmful, health_goal, language)

    # Call Gemini API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=12)
        if response.status_code == 200:
            result = response.json()
            text_response = result['candidates'][0]['content']['parts'][0]['text'].strip()
            return json.loads(text_response)
        else:
            logger.error(f"Gemini API returned error for diet report: {response.status_code} - {response.text}")
            return generate_mock_diet_report(avg_score, total_products, sorted_harmful, health_goal, language)
    except Exception as e:
        logger.error(f"Failed to query or parse Gemini diet report: {e}")
        return generate_mock_diet_report(avg_score, total_products, sorted_harmful, health_goal, language)

def generate_mock_diet_report(avg_score, total_products, sorted_harmful, health_goal, language):
    """
    Generate a realistic, fallback diet report.
    Supports English, Hindi, and Marathi to ensure language switching is visible
    even without an active API key.
    """
    top_harmful = [item[0] for item in sorted_harmful[:3]]
    top_harmful_names = ", ".join(top_harmful) if top_harmful else ""
    
    # Simple fallback generation
    translations = {
        'en': {
            'no_concern': "no immediate ingredients of concern",
            'analysis_good': f"Your average health score is quite high at {avg_score:.1f}/10! You have consumed {total_products} items. Your diet is very clean and aligns well with your {health_goal} goal. Keep up this healthy eating pattern!",
            'analysis_warning': f"I notice your average diet health score is {avg_score:.1f}/10, and you frequently consume items containing: {top_harmful_names or 'ingredients of concern'}. For your {health_goal} goal, it is recommended to decrease the intake of these ingredients to support your health journey.",
            'rec_sugars': "Try to replace sugary drinks with water or herbal tea.",
            'rec_fats': "Opt for healthy fats like almonds, walnuts, or olive oil instead of processed oils.",
            'rec_general': "Include more fresh vegetables and whole foods in your meals.",
            'rec_water': "Stay hydrated by drinking at least 8-10 glasses of water daily.",
            'rec_muscle': "Aim for a high protein snack like boiled eggs or roasted chickpeas after workouts.",
            'rec_diabetes': "Monitor your carbohydrate intake and prefer low glycemic index grains like oats."
        },
        'hi': {
            'no_concern': "कोई चिंताजनक सामग्री नहीं",
            'analysis_good': f"आपका औसत हेल्थ स्कोर काफी अच्छा है - {avg_score:.1f}/10! आपने {total_products} उत्पाद खाए हैं। आपका आहार स्वस्थ है और आपके {health_goal} लक्ष्य के अनुकूल है। इसे ऐसे ही जारी रखें!",
            'analysis_warning': f"मैंने ध्यान दिया कि आपका औसत डाइट हेल्थ स्कोर {avg_score:.1f}/10 है। आप अक्सर इन हानिकारक चीजों का सेवन कर रहे हैं: {top_harmful_names or 'चिंताजनक चीजें'}। अपने {health_goal} लक्ष्य के लिए, इन चीजों को कम करना आपके शरीर के लिए अच्छा होगा।",
            'rec_sugars': "मीठे कोल्ड ड्रिंक्स की जगह पानी या नारियल पानी पीने की आदत डालें।",
            'rec_fats': "तले हुए भोजन की जगह बादाम, अखरोट या उबले हुए चने खाएं।",
            'rec_general': "अपने भोजन में अधिक हरी सब्जियां और साबुत अनाज शामिल करें।",
            'rec_water': "दिन भर में कम से कम 8 से 10 गिलास पानी पीकर खुद को हाइड्रेटेड रखें।",
            'rec_muscle': "कसरत के बाद उबले अंडे का सफेद हिस्सा या प्रोटीन शेक लें।",
            'rec_diabetes': "अपने भोजन में कार्बोहाइड्रेट्स की मात्रा को नियंत्रित रखें और ओट्स जैसे साबुत अनाज खाएं।"
        },
        'mr': {
            'no_concern': "कोणतेही काळजीचे घटक नाहीत",
            'analysis_good': f"तुमचा सरासरी आरोग्य स्कोर {avg_score:.1f}/10 आहे, जो खूप चांगला आहे! तुम्ही {total_products} उत्पादने खाल्ली आहेत. तुमचा आहार तुमच्या {health_goal} ध्येयाशी सुसंगत आहे. हे असेच चालू ठेवा!",
            'analysis_warning': f"तुमचा सरासरी आहार आरोग्य स्कोर {avg_score:.1f}/10 आहे. तुम्ही वारंवार हे हानिकारक घटक असलेले पदार्थ खात आहात: {top_harmful_names or 'काळजीचे घटक'}. तुमच्या {health_goal} ध्येयासाठी, या घटकांचे प्रमाण कमी करणे शरीरासाठी फायदेशीर ठरेल.",
            'rec_sugars': "गोड पेयांऐवजी पाणी किंवा लिंबू पाणी पिण्यास सुरुवात करा.",
            'rec_fats': "तळलेले पदार्थ खाण्याऐवजी बदाम, अक्रोड किंवा ओट्स खा.",
            'rec_general': "जेवणामध्ये ताज्या भाज्या आणि फळांचे प्रमाण वाढवा.",
            'rec_water': "दिवसभरात किमान ८ ते १० ग्लास पाणी पिऊन शरीर हायड्रेटेड ठेवा.",
            'rec_muscle': "व्यायामानंतर उकडलेले अंडे किंवा प्रोटीन शेकचे सेवन करा.",
            'rec_diabetes': "साखरेचे प्रमाण नियंत्रित ठेवा आणि जेवणात चिया सीड्स किंवा ओट्स समाविष्ट करा."
        }
    }
    
    t = translations.get(language, translations['en'])
    analysis = t['analysis_good'] if avg_score >= 7.0 else t['analysis_warning']
    
    # Select 3 recommendations
    recommendations = []
    has_sugar = any(s in top_harmful_names for s in ["Sugar", "चीनी", "साखर"])
    has_fat = any(f in top_harmful_names for f in ["Fat", "वसा", "चरबी"])
    
    if has_sugar or avg_score < 6:
        recommendations.append(t['rec_sugars'])
    if has_fat:
        recommendations.append(t['rec_fats'])
        
    if health_goal == 'MUSCLE_GAIN':
        recommendations.append(t['rec_muscle'])
    elif health_goal == 'DIABETES':
        recommendations.append(t['rec_diabetes'])
    else:
        recommendations.append(t['rec_general'])
        
    recommendations.append(t['rec_water'])
    
    # Ensure exactly 3 recommendations
    while len(recommendations) < 3:
        recommendations.append(t['rec_general'])
        
    return {
        'analysis': analysis,
        'recommendations': recommendations[:3]
    }

