import re
from datetime import datetime


def extract_price(text):
    """Extrage prețul dintr-un text"""
    numbers = re.findall(r'\d+', text)
    if numbers:
        return int(numbers[0])
    return None


def extract_color(text):
    """Extrage culoarea din text"""
    colors = {
        'roșu': ['rosu', 'red', 'roz inchis'],
        'albastru': ['albastru', 'blue', 'bleumarin'],
        'verde': ['verde', 'green'],
        'negru': ['negru', 'black'],
        'alb': ['alb', 'white', 'crem'],
        'auriu': ['auriu', 'gold'],
        'argintiu': ['argintiu', 'silver']
    }

    text_lower = text.lower()
    for color, variants in colors.items():
        for variant in variants:
            if variant in text_lower:
                return color
    return None


def format_price(price):
    """Formatează prețul în format monedă"""
    return f"{price:.2f} RON"


def get_business_hours_message(config):
    """Returnează mesajul cu orele de lucru"""
    if not config or 'logistics' not in config:
        return "Luni - Vineri, 09:00 - 18:00"

    try:
        return config['logistics']['contact']['hours']
    except:
        return "Luni - Vineri, 09:00 - 18:00"


def is_business_hours(config):
    """Verifică dacă e în orele de lucru"""
    now = datetime.now()
    hour = now.hour
    day = now.weekday()  # 0=Luni, 6=Duminică

    # Luni-Vineri (0-4), 09:00-18:00
    if day < 5 and 9 <= hour < 18:
        return True
    return False


def sanitize_input(text):
    """Curață input-ul utilizatorului"""
    # Elimină caractere speciale periculoase
    text = text.strip()
    text = re.sub(r'[<>\"\'%;()&+]', '', text)
    return text[:500]  # Limită la 500 caractere


def get_greeting(hour=None):
    """Returnează un salut potrivit orei"""
    if hour is None:
        hour = datetime.now().hour

    if 6 <= hour < 12:
        return "Bună dimineața! ☀️"
    elif 12 <= hour < 18:
        return "Bună după-amiaza! 🌤️"
    elif 18 <= hour < 24:
        return "Bună seara! 🌙"
    else:
        return "Bună noaptea! 🌃"
