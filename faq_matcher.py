"""
FAQ Matcher - Matching inteligent pentru FAQ-uri cu similarity scoring
Creat pentru: Ejolie Chatbot
Data: 2026-01-18
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FAQMatcher:
    """
    Matcher inteligent pentru FAQ-uri cu:
    - Procesare text (lowercase, fără diacritice, fără punctuație)
    - Similarity scoring (exact match, contains, word overlap)
    - Nivele de răspuns (quick, standard, complete)
    - Caching pentru performanță
    """

    def __init__(self, faq_config_path: str = 'faq_config.json'):
        """
        Inițializează FAQ Matcher-ul.

        Args:
            faq_config_path: Calea către fișierul JSON cu FAQ-uri
        """
        self.faq_config_path = faq_config_path
        self.faq_data = self._load_faq_config()
        self.cache = {}  # Cache pentru matching rapid

        # Mapare diacritice românești
        self.diacritics_map = str.maketrans({
            'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
            'Ă': 'a', 'Â': 'a', 'Î': 'i', 'Ș': 's', 'Ț': 't'
        })

        logger.info(
            f"✅ FAQ Matcher initialized with {len(self.faq_data.get('categorii', []))} categories")

    def _load_faq_config(self) -> Dict:
        """Încarcă configurația FAQ din JSON."""
        try:
            with open(self.faq_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('faq_structured', {})
        except FileNotFoundError:
            logger.error(f"❌ FAQ config not found: {self.faq_config_path}")
            return {'categorii': []}
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in FAQ config: {e}")
            return {'categorii': []}

    def process_text(self, text: str) -> str:
        """
        Procesează textul pentru matching:
        - Lowercase
        - Elimină diacritice (ă→a, î→i, ș→s, ț→t)
        - Elimină punctuație
        - Elimină spații multiple

        Args:
            text: Textul de procesat

        Returns:
            str: Textul procesat
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Elimină diacritice
        text = text.translate(self.diacritics_map)

        # Elimină punctuație (păstrăm doar litere și cifre)
        text = re.sub(r'[^\w\s]', ' ', text)

        # Elimină spații multiple
        text = re.sub(r'\s+', ' ', text)

        # Trim
        text = text.strip()

        return text

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculează similaritatea între 2 texte.

        Strategii:
        1. Exact match → 100%
        2. Text1 conține text2 complet → 95%
        3. Text2 conține text1 complet → 90%
        4. Overlap de cuvinte → scor bazat pe % overlap

        Args:
            text1: Primul text (întrebarea utilizatorului)
            text2: Al doilea text (keyword din FAQ)

        Returns:
            float: Scor similaritate (0-100)
        """
        # Exact match
        if text1 == text2:
            return 100.0

        # Text1 conține text2 complet
        if text2 in text1:
            return 95.0

        # Text2 conține text1 complet
        if text1 in text2:
            return 90.0

        # Calculăm overlap de cuvinte
        words1 = set(text1.split())
        words2 = set(text2.split())

        # Cuvinte comune
        common = words1.intersection(words2)

        # Toate cuvintele unice
        total = words1.union(words2)

        if len(total) == 0:
            return 0.0

        # Scor bazat pe Jaccard similarity
        score = (len(common) / len(total)) * 100

        return round(score, 2)

    def find_best_match(self, user_question: str, threshold: float = 60.0) -> Optional[Dict]:
        """
        Găsește cel mai bun match pentru întrebarea utilizatorului.

        Args:
            user_question: Întrebarea utilizatorului
            threshold: Pragul minim de similaritate (default 60%)

        Returns:
            Dict cu informații despre match sau None
        """
        # Check cache
        cache_key = self.process_text(user_question)
        if cache_key in self.cache:
            logger.info(f"💨 Cache hit for: {user_question[:30]}...")
            return self.cache[cache_key]

        # Procesăm întrebarea
        processed_question = self.process_text(user_question)

        # Variabile pentru best match
        best_score = 0.0
        best_category = None

        # Parcurgem toate categoriile
        for category in self.faq_data.get('categorii', []):
            # Parcurgem toate keywords-urile
            for keyword in category.get('keywords', []):
                # Procesăm keyword-ul
                processed_keyword = self.process_text(keyword)

                # Calculăm similaritatea
                score = self.calculate_similarity(
                    processed_question, processed_keyword)

                # Dacă e cel mai bun match până acum
                if score > best_score:
                    best_score = score
                    best_category = category

        # Verificăm threshold
        if best_score < threshold:
            logger.info(
                f"❌ No match found (best score: {best_score}% < {threshold}%)")
            return None

        # Construim rezultatul
        result = {
            'category_id': best_category.get('id'),
            'category_name': best_category.get('nume'),
            'emoji': best_category.get('emoji', ''),
            'score': best_score,
            'responses': best_category.get('responses', {})
        }

        # Salvăm în cache
        self.cache[cache_key] = result

        logger.info(
            f"✅ Match found: {result['category_name']} (score: {best_score}%)")

        return result

    def decide_response_level(self, user_question: str) -> str:
        """
        Decide ce nivel de răspuns să returneze.

        OPTIMIZARE: Returnează ÎNTOTDEAUNA răspunsul COMPLET pentru a elibera 
        call center-ul de muncă. Utilizatorii primesc toate informațiile necesare.

        Args:
            user_question: Întrebarea utilizatorului

        Returns:
            str: "complete" (ÎNTOTDEAUNA)
        """
        # ÎNTOTDEAUNA returnăm răspunsul COMPLET
        # Astfel clienții au toate informațiile și nu mai sună la call center
        return "complete"

    def get_response(self, user_question: str, threshold: float = 60.0) -> Optional[Dict]:
        """
        Găsește răspunsul potrivit pentru întrebarea utilizatorului.

        Args:
            user_question: Întrebarea utilizatorului
            threshold: Pragul minim de similaritate

        Returns:
            Dict cu răspunsul sau None
        """
        # Găsim best match
        match = self.find_best_match(user_question, threshold)

        if not match:
            return None

        # Decidem nivelul de răspuns
        level = self.decide_response_level(user_question)

        # Extragem răspunsul
        response_text = match['responses'].get(
            level, match['responses'].get('standard', ''))

        return {
            'category_id': match['category_id'],
            'category_name': match['category_name'],
            'emoji': match['emoji'],
            'score': match['score'],
            'level': level,
            'response': response_text
        }

    def get_fallback_response(self, user_question: str) -> str:
        """
        Răspuns când nu găsim match exact.
        Încearcă cu threshold mai mic (50%) pentru sugestii.

        Args:
            user_question: Întrebarea utilizatorului

        Returns:
            str: Răspunsul fallback
        """
        # Încercăm cu threshold mai mic
        partial_match = self.find_best_match(user_question, threshold=50.0)

        if partial_match and partial_match['score'] >= 50:
            # Avem un match parțial - sugerăm
            level = "complete"  # ÎNTOTDEAUNA complete
            response = partial_match['responses'].get(
                level, partial_match['responses'].get('standard', ''))

            return f"""Cred că întrebi despre {partial_match['category_name']}.

{response}

Asta căutai? Dacă nu, reformulează te rog!"""

        # Nu avem match deloc - oferim opțiuni populare
        return """Îmi pare rău, nu am înțeles exact. 

Întrebări frecvente:
• Livrare (cost, timp)
• Retur (procedură, politică)
• Schimb (mărime, produs)
• Plată (metode disponibile)
• Tracking comandă

Pentru asistență: contact@ejolie.ro sau 0757 10 51 51"""

    def clear_cache(self):
        """Șterge cache-ul de matching."""
        self.cache = {}
        logger.info("🧹 FAQ cache cleared")

    def reload_config(self):
        """Reîncarcă configurația FAQ din fișier."""
        self.faq_data = self._load_faq_config()
        self.cache = {}
        logger.info("🔄 FAQ config reloaded")


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize matcher
    matcher = FAQMatcher('faq_config.json')

    print("=" * 60)
    print("FAQ MATCHER - TESTING")
    print("=" * 60)

    # Test questions
    test_questions = [
        "cat costa livrarea",
        "Cum fac retur?",
        "vreau sa schimb marimea",
        "pot plati cu cardul?",
        "cand ajunge comanda mea",
        "Bună!",
        "politica de retur completa",
        "transport gratuit?",
        "xyz abc 123"  # Should not match
    ]

    for question in test_questions:
        print(f"\n📝 Întrebare: \"{question}\"")
        print("-" * 60)

        result = matcher.get_response(question)

        if result:
            print(
                f"✅ Match găsit: {result['emoji']} {result['category_name']}")
            print(f"📊 Scor: {result['score']}%")
            print(f"📋 Nivel: {result['level'].upper()}")
            print(f"\n💬 Răspuns:\n{result['response']}")
        else:
            print("❌ Nu s-a găsit match")
            print(f"\n💬 Fallback:\n{matcher.get_fallback_response(question)}")

        print("-" * 60)
