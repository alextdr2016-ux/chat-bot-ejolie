import pandas as pd
import openai
import json
import logging
import os
import re
import uuid
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import db
from extended_api import extended_api

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')


class ChatBot:
    def __init__(self):
        self.products = []
        self.config = {}
        self.load_products()
        self.load_config()

        # 🎯 OPTIMIZATION: FAQ Cache (Strategy 2)
        self.faq_cache = self._build_faq_cache()

        # 🎯 OPTIMIZATION: Rate Limiting per User (Strategy 6)
        self.user_limits = {}

        # 🎯 OPTIMIZATION: Conversation Memory (Strategy 7)
        self.conversation_cache = {}

        logger.info("🤖 ChatBot initialized with optimizations")

    def _build_faq_cache(self):
        """Build FAQ cache for instant responses (no GPT call)"""
        return {
            # ═══════════════════════════════════════════
            # RETUR - Răspuns Master Complet
            # ═══════════════════════════════════════════

            'retur': """Retur — Politica completă

Cine poate returna:
- Persoane fizice și juridice — orice produs

Termen:
- 14 zile de la primire
- Produsul trebuie să ajungă în depozit în acest interval

Condiții obligatorii:
- Fără urme de purtare, spălare sau deteriorare
- Toate etichetele originale + sigiliu de securitate intact
- Ambalaj original, împachetat corespunzător
- Fără urme de murdărie, parfum, cosmetice
- Cu factura fiscală și toate accesoriile (curele, broșe etc.)

Important:
Produse cu sigiliu rupt sau fără etichete NU se acceptă

Cum returnezi:
1. Completează formularul (din cont sau "Retur fără cont")
2. Împachetează produsul în siguranță
3. Contactează orice curier (NU Poșta Română)
4. Achită costul transportului
5. Trimite la: Str. Serban Cioculescu nr. 15, Gaești

Rambursare:
- Maxim 14 zile de la procesare
- Transfer bancar în cont IBAN RON

Contact: 0757 10 51 51 | contact@ejolie.ro""",
            # ======================================================================

            'cum fac retur': """Retur — Politica completă

Cine poate returna:
- Persoane fizice și juridice — orice produs

Termen:
- 14 zile de la primire
- Produsul trebuie să ajungă în depozit în acest interval

Condiții obligatorii:
- Fără urme de purtare, spălare sau deteriorare
- Toate etichetele originale + sigiliu de securitate intact
- Ambalaj original, împachetat corespunzător
- Fără urme de murdărie, parfum, cosmetice
- Cu factura fiscală și toate accesoriile (curele, broșe etc.)

Important:
Produse cu sigiliu rupt sau fără etichete NU se acceptă

Cum returnezi:
1. Completează formularul (din cont sau "Retur fără cont")
2. Împachetează produsul în siguranță
3. Contactează orice curier (NU Poșta Română)
4. Achită costul transportului
5. Trimite la: Str. Serban Cioculescu nr. 15, Gaești

Rambursare:
- Maxim 14 zile de la procesare
- Transfer bancar în cont IBAN RON

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            # ==========================================================================

            'vreau sa fac retur': """Retur — Politica completă

Cine poate returna:
- Persoane fizice și juridice — orice produs

Termen:
- 14 zile de la primire
- Produsul trebuie să ajungă în depozit în acest interval

Condiții obligatorii:
- Fără urme de purtare, spălare sau deteriorare
- Toate etichetele originale + sigiliu de securitate intact
- Ambalaj original, împachetat corespunzător
- Fără urme de murdărie, parfum, cosmetice
- Cu factura fiscală și toate accesoriile (curele, broșe etc.)

Important:
Produse cu sigiliu rupt sau fără etichete NU se acceptă

Cum returnezi:
1. Completează formularul (din cont sau "Retur fără cont")
2. Împachetează produsul în siguranță
3. Contactează orice curier (NU Poșta Română)
4. Achită costul transportului
5. Trimite la: Str. Serban Cioculescu nr. 15, Gaești

Rambursare:
- Maxim 14 zile de la procesare
- Transfer bancar în cont IBAN RON

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            # =====================================================================

            'pot returna': """Retur — Politica completă

Cine poate returna:
- Persoane fizice și juridice — orice produs

Termen:
- 14 zile de la primire
- Produsul trebuie să ajungă în depozit în acest interval

Condiții obligatorii:
- Fără urme de purtare, spălare sau deteriorare
- Toate etichetele originale + sigiliu de securitate intact
- Ambalaj original, împachetat corespunzător
- Fără urme de murdărie, parfum, cosmetice
- Cu factura fiscală și toate accesoriile (curele, broșe etc.)

Important:
Produse cu sigiliu rupt sau fără etichete NU se acceptă

Cum returnezi:
1. Completează formularul (din cont sau "Retur fără cont")
2. Împachetează produsul în siguranță
3. Contactează orice curier (NU Poșta Română)
4. Achită costul transportului
5. Trimite la: Str. Serban Cioculescu nr. 15, Gaești

Rambursare:
- Maxim 14 zile de la procesare
- Transfer bancar în cont IBAN RON

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            # =====================================================================

            'politica retur': """Retur — Politica completă

Cine poate returna:
- Persoane fizice și juridice — orice produs

Termen:
- 14 zile de la primire
- Produsul trebuie să ajungă în depozit în acest interval

Condiții obligatorii:
- Fără urme de purtare, spălare sau deteriorare
- Toate etichetele originale + sigiliu de securitate intact
- Ambalaj original, împachetat corespunzător
- Fără urme de murdărie, parfum, cosmetice
- Cu factura fiscală și toate accesoriile (curele, broșe etc.)

Important:
Produse cu sigiliu rupt sau fără etichete NU se acceptă

Cum returnezi:
1. Completează formularul (din cont sau "Retur fără cont")
2. Împachetează produsul în siguranță
3. Contactează orice curier (NU Poșta Română)
4. Achită costul transportului
5. Trimite la: Str. Serban Cioculescu nr. 15, Gaești

Rambursare:
- Maxim 14 zile de la procesare
- Transfer bancar în cont IBAN RON

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            # =====================================================================

            'returnare produse': """Retur — Politica completă

Cine poate returna:
- Persoane fizice și juridice — orice produs

Termen:
- 14 zile de la primire
- Produsul trebuie să ajungă în depozit în acest interval

Condiții obligatorii:
- Fără urme de purtare, spălare sau deteriorare
- Toate etichetele originale + sigiliu de securitate intact
- Ambalaj original, împachetat corespunzător
- Fără urme de murdărie, parfum, cosmetice
- Cu factura fiscală și toate accesoriile (curele, broșe etc.)

Important:
Produse cu sigiliu rupt sau fără etichete NU se acceptă

Cum returnezi:
1. Completează formularul (din cont sau "Retur fără cont")
2. Împachetează produsul în siguranță
3. Contactează orice curier (NU Poșta Română)
4. Achită costul transportului
5. Trimite la: Str. Serban Cioculescu nr. 15, Gaești

Rambursare:
- Maxim 14 zile de la procesare
- Transfer bancar în cont IBAN RON

Contact: 0757 10 51 51 | contact@ejolie.ro""",


            # ═══════════════════════════════════════════
            # SCHIMB - Răspuns Master Complet
            # ═══════════════════════════════════════════

            'schimb': """Schimb — Politica completă

Cum soliciți:
- Din contul de client
- Email: contact@ejolie.ro

Costuri:
- Retur produs original: GRATUIT (suportat de Ejolie) ✓
- Livrare produs nou: 19 lei (suportat de client)

Diferențe de preț:
- Produs mai scump → plătești diferența la livrare
- Produs mai ieftin → primești diferența în cont bancar

Limite schimburi:
- Primul schimb: retur gratuit + 19 lei livrare
- Al doilea schimb: 38 lei total (toate costurile pe tine)
- Al treilea schimb: NU se acceptă

Condiții:
- Produs nepurtat, cu etichete și sigiliu intact
- În 14 zile de la primire
- Aceleași condiții ca la retur

Situații speciale:
- Produs defect sau incomplet → anunță în max. 24h
- Înlocuire gratuită (în limita stocului)
- Dacă indisponibil, alegi alt produs

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            'cum fac schimb': """Schimb — Politica completă

Cum soliciți:
- Din contul de client
- Email: contact@ejolie.ro

Costuri:
- Retur produs original: GRATUIT (suportat de Ejolie) ✓
- Livrare produs nou: 19 lei (suportat de client)

Diferențe de preț:
- Produs mai scump → plătești diferența la livrare
- Produs mai ieftin → primești diferența în cont bancar

Limite schimburi:
- Primul schimb: retur gratuit + 19 lei livrare
- Al doilea schimb: 38 lei total (toate costurile pe tine)
- Al treilea schimb: NU se acceptă

Condiții:
- Produs nepurtat, cu etichete și sigiliu intact
- În 14 zile de la primire
- Aceleași condiții ca la retur

Situații speciale:
- Produs defect sau incomplet → anunță în max. 24h
- Înlocuire gratuită (în limita stocului)
- Dacă indisponibil, alegi alt produs

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            'vreau sa fac schimb': """Schimb — Politica completă

Cum soliciți:
- Din contul de client
- Email: contact@ejolie.ro

Costuri:
- Retur produs original: GRATUIT (suportat de Ejolie) ✓
- Livrare produs nou: 19 lei (suportat de client)

Diferențe de preț:
- Produs mai scump → plătești diferența la livrare
- Produs mai ieftin → primești diferența în cont bancar

Limite schimburi:
- Primul schimb: retur gratuit + 19 lei livrare
- Al doilea schimb: 38 lei total (toate costurile pe tine)
- Al treilea schimb: NU se acceptă

Condiții:
- Produs nepurtat, cu etichete și sigiliu intact
- În 14 zile de la primire
- Aceleași condiții ca la retur

Situații speciale:
- Produs defect sau incomplet → anunță în max. 24h
- Înlocuire gratuită (în limita stocului)
- Dacă indisponibil, alegi alt produs

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            'pot face schimb': """Schimb — Politica completă

Cum soliciți:
- Din contul de client
- Email: contact@ejolie.ro

Costuri:
- Retur produs original: GRATUIT (suportat de Ejolie) ✓
- Livrare produs nou: 19 lei (suportat de client)

Diferențe de preț:
- Produs mai scump → plătești diferența la livrare
- Produs mai ieftin → primești diferența în cont bancar

Limite schimburi:
- Primul schimb: retur gratuit + 19 lei livrare
- Al doilea schimb: 38 lei total (toate costurile pe tine)
- Al treilea schimb: NU se acceptă

Condiții:
- Produs nepurtat, cu etichete și sigiliu intact
- În 14 zile de la primire
- Aceleași condiții ca la retur

Situații speciale:
- Produs defect sau incomplet → anunță în max. 24h
- Înlocuire gratuită (în limita stocului)
- Dacă indisponibil, alegi alt produs

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            'schimb produs': """Schimb — Politica completă

Cum soliciți:
- Din contul de client
- Email: contact@ejolie.ro

Costuri:
- Retur produs original: GRATUIT (suportat de Ejolie) ✓
- Livrare produs nou: 19 lei (suportat de client)

Diferențe de preț:
- Produs mai scump → plătești diferența la livrare
- Produs mai ieftin → primești diferența în cont bancar

Limite schimburi:
- Primul schimb: retur gratuit + 19 lei livrare
- Al doilea schimb: 38 lei total (toate costurile pe tine)
- Al treilea schimb: NU se acceptă

Condiții:
- Produs nepurtat, cu etichete și sigiliu intact
- În 14 zile de la primire
- Aceleași condiții ca la retur

Situații speciale:
- Produs defect sau incomplet → anunță în max. 24h
- Înlocuire gratuită (în limita stocului)
- Dacă indisponibil, alegi alt produs

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            'schimb marime': """Schimb — Politica completă

Cum soliciți:
- Din contul de client
- Email: contact@ejolie.ro

Costuri:
- Retur produs original: GRATUIT (suportat de Ejolie) ✓
- Livrare produs nou: 19 lei (suportat de client)

Diferențe de preț:
- Produs mai scump → plătești diferența la livrare
- Produs mai ieftin → primești diferența în cont bancar

Limite schimburi:
- Primul schimb: retur gratuit + 19 lei livrare
- Al doilea schimb: 38 lei total (toate costurile pe tine)
- Al treilea schimb: NU se acceptă

Condiții:
- Produs nepurtat, cu etichete și sigiliu intact
- În 14 zile de la primire
- Aceleași condiții ca la retur

Situații speciale:
- Produs defect sau incomplet → anunță în max. 24h
- Înlocuire gratuită (în limita stocului)
- Dacă indisponibil, alegi alt produs

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            # Livrare
            'livrare': """📦 Livrare în toată România cu GLS Courier si Sameday

            Cost:
            - 19 lei
            - GRATUIT peste 200 lei

            Timp de livrare:
            - Produse standard: 1-2 zile lucrătoare
            - Produse TRENDYA: 5-7 zile lucrătoare

            Contact: 0757 10 51 51""",

            'cat costa livrarea': "📦 Livrarea costă 19 lei în toată România. GRATUIT pentru comenzi peste 200 lei!",

            'transport': "📦 Transport: 19 lei (GRATUIT >200 lei). Timp: 1-2 zile (standard) sau 5-7 zile (TRENDYA).",

            'livrare gratuita': "📦 Da! Livrare GRATUITĂ pentru comenzi peste 200 lei. Sub 200 lei: 19 lei.",

            'cat timp livrare': """📦 Timp de livrare:
            - Produse standard: 1-2 zile lucrătoare
            - Produse TRENDYA: 5-7 zile lucrătoare""",

            'in cat timp': """📦 Livrare:
            - Produse standard: 1-2 zile
            - Produse TRENDYA: 5-7 zile""",

            'cand ajunge': """📦 Coletul ajunge:
            - Produse standard: în 1-2 zile lucrătoare
            - Produse TRENDYA: în 5-7 zile lucrătoare""",

            'cand primesc': """📦 Vei primi coletul:
            - Produse standard: în 1-2 zile
            - Produse TRENDYA: în 5-7 zile""",

            'durata livrare': """📦 Durata de livrare:
            - Produse standard: 1-2 zile lucrătoare
            - Produse TRENDYA: 5-7 zile lucrătoare""",

            # Plata
            'plata': "💳 Poți plăti: Card online, Ramburs la livrare, Transfer bancar.",
            'metode plata': "💳 Acceptăm: Card (Visa, Mastercard), Ramburs, Transfer bancar.",
            'card': "💳 Da, acceptăm plata cu cardul online (Visa, Mastercard).",
            'ramburs': "💳 Da, acceptăm plata ramburs la livrare!",

            # ═══════════════════════════════════════════
            # MĂRIMI - Tabel oficial (cu toleranță)
            # ═══════════════════════════════════════════

            'marimi': """Mărimi — Tabel oficial (cm)

Mărime | Bust | Talie | Șold
36 | 88 | 70 | 94
38 | 92 | 74 | 98
40 | 96 | 78 | 102
42 | 100 | 82 | 106
44 | 104 | 86 | 110
46 | 108 | 90 | 114
48 | 112 | 94 | 118

❗ Dimensiunile pot varia cu ±1-2 cm

Cum măsori:
- Bust: Măsoară în jurul părții celei mai largi
- Talie: Măsoară în zona cea mai îngustă
- Șold: Măsoară în jurul părții celei mai largi

Contact: 0757 10 51 51""",

            'ghid marimi': """Ghid mărimi — Tabel complet

Mărime 36: Bust 88 | Talie 70 | Șold 94 cm
Mărime 38: Bust 92 | Talie 74 | Șold 98 cm
Mărime 40: Bust 96 | Talie 78 | Șold 102 cm
Mărime 42: Bust 100 | Talie 82 | Șold 106 cm
Mărime 44: Bust 104 | Talie 86 | Șold 110 cm
Mărime 46: Bust 108 | Talie 90 | Șold 114 cm
Mărime 48: Bust 112 | Talie 94 | Șold 118 cm

❗ Toleranță: ±1-2 cm la fiecare măsură

Pentru a alege mărimea corectă, măsoară-te și compară cu tabelul.

Contact: 0757 10 51 51""",

            'tabel marimi': """Tabel mărimi (cm)

Mărime | Bust | Talie | Șold
36 | 88 | 70 | 94
38 | 92 | 74 | 98
40 | 96 | 78 | 102
42 | 100 | 82 | 106
44 | 104 | 86 | 110
46 | 108 | 90 | 114
48 | 112 | 94 | 118

❗ Dimensiunile pot varia cu ±1-2 cm""",

            'ce marime': """Ce mărime să aleg?

Măsoară-te și compară cu ghidul nostru:
- Bust (cm) → partea cea mai largă
- Talie (cm) → zona cea mai îngustă
- Șold (cm) → partea cea mai largă

Dacă ești între 2 mărimi:
- Pentru fit confortabil → mărimea mai mare
- Pentru fit ajustat → mărimea mai mică

Scrie "ghid mărimi" pentru tabel complet.""",

            'marime 36': """Mărimea 36 (XS)

Dimensiuni:
- Bust: 88 cm
- Talie: 70 cm
- Șold: 94 cm

Echivalent:
- XS
- UK: 8
- US: 4

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime 38': """Mărimea 38 (S)

Dimensiuni:
- Bust: 92 cm
- Talie: 74 cm
- Șold: 98 cm

Echivalent:
- S
- UK: 10
- US: 6

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime 40': """Mărimea 40 (M)

Dimensiuni:
- Bust: 96 cm
- Talie: 78 cm
- Șold: 102 cm

Echivalent:
- M
- UK: 12
- US: 8

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime 42': """Mărimea 42 (L)

Dimensiuni:
- Bust: 100 cm
- Talie: 82 cm
- Șold: 106 cm

Echivalent:
- L
- UK: 14
- US: 10

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime 44': """Mărimea 44 (XL)

Dimensiuni:
- Bust: 104 cm
- Talie: 86 cm
- Șold: 110 cm

Echivalent:
- XL
- UK: 16
- US: 12

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime 46': """Mărimea 46 (XXL)

Dimensiuni:
- Bust: 108 cm
- Talie: 90 cm
- Șold: 114 cm

Echivalent:
- XXL
- UK: 18
- US: 14

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime 48': """Mărimea 48 (XXXL)

Dimensiuni:
- Bust: 112 cm
- Talie: 94 cm
- Șold: 118 cm

Echivalent:
- XXXL / 3XL
- UK: 20
- US: 16

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime s': """Mărimea S (38)

Dimensiuni:
- Bust: 92 cm
- Talie: 74 cm
- Șold: 98 cm

Echivalent EU: 38

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime m': """Mărimea M (40)

Dimensiuni:
- Bust: 96 cm
- Talie: 78 cm
- Șold: 102 cm

Echivalent EU: 40

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime l': """Mărimea L (42)

Dimensiuni:
- Bust: 100 cm
- Talie: 82 cm
- Șold: 106 cm

Echivalent EU: 42

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'marime xl': """Mărimea XL (44)

Dimensiuni:
- Bust: 104 cm
- Talie: 86 cm
- Șold: 110 cm

Echivalent EU: 44

❗ Toleranță: ±1-2 cm

Scrie "cum măsor" pentru ghid măsurare.""",

            'cum masor': """Cum să măsori corect

Bust:
- Măsoară în jurul părții celei mai largi a bustului
- Banda trebuie să fie paralelă cu solul
- Nu strânge banda

Talie:
- Măsoară în jurul taliei naturale (zona cea mai îngustă)
- Relaxează abdomenul
- Banda trebuie să fie confortabilă

Șold:
- Măsoară în jurul părții celei mai largi a șoldurilor
- Include și fesele
- Banda paralelă cu solul

Sfat: Măsoară-te în lenjerie pentru acuratețe maximă.""",

            'cum se potriveste': """Fitting — Cum se potrivește

Produsele noastre au fit-uri diferite:

Regular fit:
- Nici strâmt, nici larg
- Confortabil pentru zi cu zi
- Permite libertate de mișcare

Fitted/Slim fit:
- Mai ajustat pe corp
- Subliniază silueta
- Perfect pentru ținute elegante

Loose/Oversized fit:
- Mai larg, relaxat
- Confort maxim
- Stil casual, modern

Pentru detalii despre un produs specific, întreabă "cum se potrivește [nume produs]".""",

            'intre doua marimi': """Între două mărimi?

Dacă măsurătorile tale se încadrează între 2 mărimi:

Pentru fit confortabil:
- Alege mărimea mai mare
- Mai multă libertate de mișcare
- Perfect pentru stil relaxat

Pentru fit ajustat:
- Alege mărimea mai mică
- Mai mulat pe corp
- Perfect pentru ținute elegante

Sfat: Pentru produse stretch/elastice, poți lua mărimea mai mică.""",

            'size': """Size guide (cm)

Size | Bust | Waist | Hip
36 | 88 | 70 | 94
38 | 92 | 74 | 98
40 | 96 | 78 | 102
42 | 100 | 82 | 106
44 | 104 | 86 | 110
46 | 108 | 90 | 114
48 | 112 | 94 | 118

❗ Dimensions may vary ±1-2 cm

Contact: 0757 10 51 51""",

            # Contact

            # Contact
            'contact': "📧 Email: contact@ejolie.ro | 📞 Telefon: 0757 10 51 51 | 🌐 https://ejolie.ro",
            'email': "📧 contact@ejolie.ro",
            'telefon': "📱 0757 10 51 51",

            # Program
            'program': "🕐 Programul nostru: Luni-Vineri 9:00-18:00. Comenzi online 24/7!",
            'orar': "🕐 Luni-Vineri 9:00-18:00.",

            # ═══════════════════════════════════════════
            # COMENZI - Order tracking
            # ═══════════════════════════════════════════

            'comanda mea': """Pentru a verifica statusul comenzii tale, te rog să-mi dai numărul comenzii.

Exemplu: "comanda #12345" sau "unde e comanda 12345"

Poți găsi numărul comenzii în:
- Email-ul de confirmare
- Contul tău de client

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            'unde e comanda': """Pentru a verifica statusul comenzii tale, te rog să-mi dai numărul comenzii.

Exemplu: "comanda #12345" sau "unde e comanda 12345"

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            'status comanda': """Pentru a verifica statusul comenzii tale, te rog să-mi dai numărul comenzii.

Exemplu: "comanda #12345"

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            'tracking': """Pentru tracking AWB, te rog să-mi dai numărul comenzii.

Exemplu: "comanda #12345"

Contact: 0757 10 51 51 | contact@ejolie.ro""",

            # Generale
            'salut': "👋 Bună! Sunt Maria, asistenta virtuală ejolie.ro. Cu ce te pot ajuta?",
            'buna': "👋 Buna! Cu ce te pot ajuta astăzi?",
            'hello': "👋 Hello! How can I help you?",
        }

    def load_products(self):
        """Load products from CSV feed"""
        if not os.path.exists('products.csv'):
            self.products = []
            return

        try:
            df = pd.read_csv('products.csv', encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv('products.csv', encoding='latin-1')
        except Exception as e:
            logger.error(f"❌ Error reading products.csv: {e}")
            self.products = []
            return

        self.products = []
        logger.info(f"📋 CSV Columns found: {list(df.columns)}")

        for _, row in df.iterrows():
            name = str(row.get('Nume', '')).strip()

            try:
                price_raw = row.get('Pret vanzare (cu promotie)', 0)
                if pd.isna(price_raw):
                    price = 0.0
                else:
                    price_str = str(price_raw).replace(
                        'RON', '').replace(',', '.').strip()
                    price = float(price_str)
            except:
                price = 0.0

            desc = str(row.get('Descriere', '')).strip()

            try:
                stock_raw = row.get('Stoc numeric', 0)
                if pd.isna(stock_raw):
                    stock = 0
                else:
                    stock = int(stock_raw)
            except:
                stock = 0

            link = str(row.get('Link produs', '')).strip()
            image_link = str(row.get('Imagine (principala)',
                             row.get('image_link', ''))).strip()

            if name and price > 0:
                self.products.append(
                    (name, price, desc, stock, link, image_link))

        logger.info(f"✅ Loaded {len(self.products)} products from feed")

        if self.products:
            sample = self.products[0]
            logger.info(
                f"📦 Sample: {sample[0][:30]}, {sample[1]} RON, stock={sample[3]}")

    def load_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception:
            self.config = {}

    # 🎯 NEW: Category Detection
    def detect_category(self, user_message):
        """Detect product category from user message"""
        message_lower = user_message.lower()

        # Priority order (check specific first)
        if any(word in message_lower for word in ['compleu', 'compleuri', 'costum', 'costume', 'set']):
            return 'compleuri'
        elif any(word in message_lower for word in ['camasa', 'camasi', 'cămașă', 'cămași', 'bluza', 'bluze']):
            return 'camasi'
        elif any(word in message_lower for word in ['pantalon', 'pantaloni', 'blugi', 'jeans']):
            return 'pantaloni'
        elif any(word in message_lower for word in ['rochie', 'rochii', 'dress']):
            return 'rochii'
        else:
            return 'general'

    def deduplicate_products(self, products, category=None):
        """Remove duplicates (same item, different colors/sizes)"""
        seen_base_names = set()
        unique = []

        for product in products:
            name = product[0].lower() if product[0] else ''
            base_name = name

            # Remove colors
            colors = [
                'neagra', 'neagră', 'negru',
                'alba', 'albă', 'alb',
                'rosie', 'roșie', 'rosu', 'roșu',
                'albastra', 'albastră', 'albastru',
                'verde', 'verzi',
                'bordo', 'burgundy',
                'aurie', 'auriu',
                'galbena', 'galbenă', 'galben',
                'maro', 'maroniu',
                'bej', 'crem',
                'bleu', 'blue',
                'turcoaz',
                'mov', 'violet', 'lila',
                'portocaliu', 'orange',
                'roz', 'pink'
            ]

            # 🎯 NEW: Remove sizes
            sizes = ['xs', 'x s', 's', 'm', 'l', 'xl', 'x l', 'xxl', 'x x l',
                     'marime s', 'marime m', 'marime l', 'marime xl']

            for color in colors:
                base_name = re.sub(r'\b' + color + r'\b', '',
                                   base_name, flags=re.IGNORECASE)

            for size in sizes:
                base_name = re.sub(r'\b' + size + r'\b', '',
                                   base_name, flags=re.IGNORECASE)

            base_name = ' '.join(base_name.split()).strip()

            if base_name and base_name not in seen_base_names:
                seen_base_names.add(base_name)
                unique.append(product)

        logger.info(f"🔍 Deduplication: {len(products)} → {len(unique)} unique")
        return unique

    def extract_price_range(self, query):
        """Extract price range from query"""
        patterns = [
            r'sub\s+(\d+)',
            r'pana\s+la\s+(\d+)',
            r'mai\s+ieftin\s+de\s+(\d+)',
            r'under\s+(\d+)',
            r'(\d+)\s+ron',
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return float(match.group(1))

        return None

    def extract_price_range_advanced(self, query):
        """Extract price range (single limit or range)"""
        query_lower = query.lower()

        # Range: 100-200, între 100 și 200
        range_patterns = [
            r'(\d+)\s*-\s*(\d+)',  # 100-200
            r'intre\s+(\d+)\s+si\s+(\d+)',  # între 100 și 200
            r'intre\s+(\d+)\s+(\d+)',  # între 100 200
            r'de\s+la\s+(\d+)\s+la\s+(\d+)',  # de la 100 la 200
        ]

        for pattern in range_patterns:
            match = re.search(pattern, query_lower)
            if match:
                return {
                    'min': float(match.group(1)),
                    'max': float(match.group(2))
                }

        # Single limit (sub, peste, mai ieftin de)
        single_patterns = [
            (r'sub\s+(\d+)', 'max'),
            (r'pana\s+la\s+(\d+)', 'max'),
            (r'mai\s+ieftin\s+de\s+(\d+)', 'max'),
            (r'maxim\s+(\d+)', 'max'),
            (r'peste\s+(\d+)', 'min'),
            (r'mai\s+scump\s+de\s+(\d+)', 'min'),
            (r'minim\s+(\d+)', 'min'),
        ]

        for pattern, limit_type in single_patterns:
            match = re.search(pattern, query_lower)
            if match:
                value = float(match.group(1))
                if limit_type == 'max':
                    return {'max': value}
                else:
                    return {'min': value}

        return None

    def extract_materials(self, query):
        """Extract material filters from query"""
        query_lower = query.lower()

        materials_map = {
            'catifea': ['catifea', 'velur', 'velvet'],
            'dantela': ['dantela', 'dantelă', 'lace'],
            'matase': ['matase', 'mătase', 'silk'],
            'bumbac': ['bumbac', 'cotton'],
            'in': ['in', 'în', 'linen'],
            'poliester': ['poliester', 'polyester'],
            'vascoza': ['vascoza', 'viscoză', 'viscose'],
            'piele': ['piele', 'leather'],
            'lana': ['lana', 'lână', 'wool']
        }

        detected_materials = []
        for material, keywords in materials_map.items():
            if any(kw in query_lower for kw in keywords):
                detected_materials.append(material)

        return detected_materials

    def extract_colors_multiple(self, query):
        """Extract multiple colors from query"""
        query_lower = query.lower()

        colors_map = {
            'neagra': ['neagra', 'neagră', 'negru', 'black'],
            'alba': ['alba', 'albă', 'alb', 'white'],
            'rosie': ['rosie', 'roșie', 'rosu', 'roșu', 'red'],
            'albastra': ['albastra', 'albastră', 'albastru', 'blue'],
            'verde': ['verde', 'green'],
            'bordo': ['bordo', 'burgundy', 'visiniu'],
            'aurie': ['aurie', 'auriu', 'gold'],
            'galbena': ['galbena', 'galbenă', 'galben', 'yellow'],
            'maro': ['maro', 'maroniu', 'brown'],
            'bej': ['bej', 'crem', 'beige', 'cream'],
            'turcoaz': ['turcoaz', 'turquoise'],
            'mov': ['mov', 'violet', 'lila', 'purple'],
            'roz': ['roz', 'pink'],
            'portocaliu': ['portocaliu', 'orange']
        }

        detected_colors = []
        for color, keywords in colors_map.items():
            if any(kw in query_lower for kw in keywords):
                detected_colors.append(color)

        return detected_colors

    def extract_sort_preference(self, query):
        """Extract sorting preference"""
        query_lower = query.lower()

        # Cheapest first
        if any(kw in query_lower for kw in ['ieftin', 'mai ieftin', 'cele mai ieftine', 'pret mic']):
            return 'price_asc'

        # Most expensive first
        if any(kw in query_lower for kw in ['scump', 'mai scump', 'cele mai scumpe', 'pret mare']):
            return 'price_desc'

        # Newest first
        if any(kw in query_lower for kw in ['nou', 'noi', 'cele mai noi', 'ultimele']):
            return 'newest'

        return None

    def extract_order_number(self, query):
        """Extract order number from query"""
        query_lower = query.lower()

        # Patterns for order detection
        patterns = [
            r'comanda\s*#?(\d+)',
            r'comanda\s+nr\s*\.?\s*(\d+)',
            r'order\s*#?(\d+)',
            r'nr\s*\.?\s*comanda\s*:?\s*(\d+)',
            r'(?:unde|status|tracking).*?(\d{5,})',  # 5+ digits
        ]

        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                order_id = match.group(1)
                logger.info(f"📦 Detected order ID: {order_id}")
                return order_id

        return None

    def format_order_response(self, order_data):
        """Format order data into elegant response"""
        if not order_data:
            return None

        response = f"""Comanda #{order_data['id']}

Status: {order_data['status']}
Data: {order_data['data']}

Detalii:
- Produse: {order_data['produse_count']} articole
- Total: {order_data['total']} RON
- Livrare: {order_data['metoda_livrare']} ({order_data['livrare_cost']} RON)
- Plată: {order_data['metoda_plata']}"""

        # Add AWB info if available
        if order_data['awb']:
            response += f"\n\nTracking AWB:"
            response += f"\n• Număr: {order_data['awb']}"
            response += f"\n• Status: {order_data['awb_status']}"

            if order_data['awb_link']:
                response += f"\n• Link tracking: {order_data['awb_link']}"

            # Add tracking stages if available
            if order_data['stadii'] and len(order_data['stadii']) > 0:
                response += f"\n\nIstoric livrare:"
                # stadii is a dict, convert to list and get last 3
                stadii_list = list(order_data['stadii'].values())
                for stadiu in stadii_list[:3]:  # Show last 3 stages
                    status_text = stadiu.get('status', '')
                    data_text = stadiu.get('data', '')
                    response += f"\n• {status_text} - {data_text}"

        response += f"\n\nContact: 0757 10 51 51 | contact@ejolie.ro"

        return response

    def search_products(self, query, limit=3, max_price=None, category=None, price_range=None, materials=None, colors=None, sort_by=None):
        """Search products with advanced filtering"""
        if not self.products:
            return []

        # Detect category if not specified
        if category is None:
            category = self.detect_category(query)

        query_lower = query.lower()

        # Category-specific keywords
        category_keywords = {
            'rochii': ['rochie', 'rochii', 'dress'],
            'compleuri': ['compleu', 'compleuri', 'costum', 'set'],
            'camasi': ['camasa', 'camasi', 'cămașă', 'bluza'],
            'pantaloni': ['pantalon', 'pantaloni', 'blugi', 'jeans']
        }

        stop_words = {'sub', 'peste', 'vreau', 'caut', 'imi', 'trebuie',
                      'doresc', 'lei', 'ron', 'pentru', 'cu', 'de', 'la', 'in', 'si', 'sau'}
        keywords = [w.strip() for w in query_lower.split() if w.strip(
        ) and w.strip() not in stop_words and not w.strip().isdigit()]

        color_normalizations = {
            'rosii': 'rosie', 'roșii': 'rosie',
            'negre': 'neagra', 'negru': 'neagra',
            'albe': 'alba', 'alb': 'alba',
            'verzi': 'verde',
        }

        normalized_keywords = [
            color_normalizations.get(kw, kw) for kw in keywords]

        results = []

        for product in self.products:
            name = product[0].lower() if product[0] else ''
            desc = product[2].lower() if product[2] else ''
            price = product[1]

            score = 0

            # Keyword matching
            for keyword in normalized_keywords:
                if keyword in name:
                    score += 10
                elif keyword in desc:
                    score += 5

            # 🎯 NEW: Category bonus
            if category in category_keywords:
                for cat_kw in category_keywords[category]:
                    if cat_kw in name:
                        score += 5

            # Price filtering
            if max_price is not None and price > max_price:
                score = 0

            # 🎯 ADVANCED FILTERS

            # Price range filter
            if price_range:
                if 'min' in price_range and price < price_range['min']:
                    score = 0
                if 'max' in price_range and price > price_range['max']:
                    score = 0

            # Material filter
            if materials and score > 0:
                material_found = False
                for material in materials:
                    if material in desc or material in name:
                        score += 3  # Bonus for material match
                        material_found = True
                        break
                if not material_found:
                    score = 0  # Exclude if material not found

            # Color filter (multiple colors OR logic)
            if colors and score > 0:
                color_found = False
                for color in colors:
                    if color in name or color in desc:
                        score += 2  # Bonus for color match
                        color_found = True
                if not color_found:
                    score = 0  # Exclude if no color match

            if score > 0:
                results.append((product, score))

        results.sort(key=lambda x: x[1], reverse=True)

        # 🎯 SORTING
        if sort_by == 'price_asc':
            results.sort(key=lambda x: x[0][1])  # Sort by price ascending
        elif sort_by == 'price_desc':
            # Sort by price descending
            results.sort(key=lambda x: x[0][1], reverse=True)

        return [p[0] for p in results[:limit]]

    def is_in_stock(self, product):
        if len(product) >= 4:
            return product[3] > 0
        return True

    def search_products_in_stock(self, query, limit=4, category=None, deduplicate=True):
        """Search with optional deduplication and advanced filters"""

        # 🎯 Extract all filters
        price_range = self.extract_price_range_advanced(query)
        materials = self.extract_materials(query)
        colors = self.extract_colors_multiple(query)
        sort_by = self.extract_sort_preference(query)

        # Log detected filters
        if price_range:
            logger.info(f"💰 Price range: {price_range}")
        if materials:
            logger.info(f"🧵 Materials: {materials}")
        if colors:
            logger.info(f"🎨 Colors: {colors}")
        if sort_by:
            logger.info(f"🔢 Sort by: {sort_by}")

        all_results = self.search_products(
            query,
            limit * 3,
            category=category,
            price_range=price_range,
            materials=materials,
            colors=colors,
            sort_by=sort_by
        )

        if all_results:
            in_stock = [p for p in all_results if self.is_in_stock(p)]

            if in_stock:
                if deduplicate:
                    unique_products = self.deduplicate_products(
                        in_stock, category)
                    return unique_products[:limit]
                else:
                    # Show ALL color variants
                    return in_stock[:limit]
            else:
                logger.warning(f"⚠️ No in-stock products for '{query}'")
                if deduplicate:
                    unique_products = self.deduplicate_products(
                        all_results, category)
                    return unique_products[:limit]
                else:
                    return all_results[:limit]

        # 🎯 FIX: Return empty list if no results
        return []

    def get_delivery_time(self, product_name):
        """Return delivery time based on brand"""
        if product_name and 'trendya' in product_name.lower():
            return "5-7 zile lucrătoare"
        else:
            return "1-2 zile lucrătoare"

    # 🎯 OPTIMIZATION: Short product context (Strategy 3)
    def format_products_for_context_short(self, products):
        """SHORT product context for GPT (save tokens!)"""
        if not products:
            return "Niciun produs găsit."

        # Just essentials: name, price, stock
        lines = []
        for i, p in enumerate(products, 1):
            stock = "✅" if p[3] > 0 else "❌"
            lines.append(f"{i}. {p[0]} - {p[1]} RON {stock}")

        return "\n".join(lines)

    # 🎯 NEW: Contextual messages per category
    def get_contextual_message(self, user_message, category=None):
        """Generate short message based on category and context"""
        if category is None:
            category = self.detect_category(user_message)

        message_lower = user_message.lower()

        # ROCHII
        if category == 'rochii':
            if "nunta" in message_lower or "eveniment" in message_lower:
                return "🎉 Iată rochii elegante pentru eveniment:"
            elif "casual" in message_lower:
                return "👗 Iată rochii casual:"
            elif "seara" in message_lower or "party" in message_lower:
                return "✨ Iată rochii de seară:"
            else:
                return "👗 Iată câteva rochii pentru tine:"

        # COMPLEURI
        elif category == 'compleuri':
            if "birou" in message_lower or "office" in message_lower:
                return "💼 Iată compleuri elegante pentru birou:"
            elif "casual" in message_lower:
                return "👔 Iată compleuri casual:"
            else:
                return "👔 Iată câteva compleuri pentru tine:"

        # CAMASI
        elif category == 'camasi':
            if "eleganta" in message_lower or "elegante" in message_lower:
                return "👕 Iată cămăși elegante:"
            else:
                return "👕 Iată câteva cămăși pentru tine:"

        # PANTALONI
        elif category == 'pantaloni':
            if "blugi" in message_lower or "jeans" in message_lower:
                return "👖 Iată blugi pentru tine:"
            else:
                return "👖 Iată câtiva pantaloni pentru tine:"

        # GENERAL
        else:
            return "🎀 Iată câteva produse pentru tine:"

    # 🎯 OPTIMIZATION: FAQ Cache Check (Strategy 2)
    def check_faq_cache(self, user_message):
        """Check if message matches FAQ - return cached response"""
        message_lower = user_message.lower().strip()
        clean_msg = message_lower.replace('?', '').replace('.', '').strip()

        # Exact match
        if clean_msg in self.faq_cache:
            logger.info(f"💾 FAQ Cache HIT: {clean_msg[:30]}")
            return self.faq_cache[clean_msg]

        # Partial match
        for key, response in self.faq_cache.items():
            if key in clean_msg:
                logger.info(f"💾 FAQ Cache PARTIAL HIT: {key}")
                return response

        return None

    # 🎯 OPTIMIZATION: Rate Limiting (Strategy 6)
    def check_rate_limit(self, session_id):
        """Check if user exceeded personal limit (10 req/min)"""
        now = time.time()

        if session_id not in self.user_limits:
            self.user_limits[session_id] = []

        # Clean old requests (older than 1 minute)
        self.user_limits[session_id] = [
            req_time for req_time in self.user_limits[session_id]
            if now - req_time < 60
        ]

        # Check limit: max 10 requests per minute
        if len(self.user_limits[session_id]) >= 10:
            logger.warning(
                f"⚠️ Rate limit exceeded for session: {session_id[:8]}")
            return False

        # Add current request
        self.user_limits[session_id].append(now)
        return True

    # 🎯 OPTIMIZATION: Conversation Memory (Strategy 7)
    def is_followup_question(self, message):
        """Detect if referring to previous results"""
        followup_patterns = [
            'prima', 'primul', 'a doua', 'al doilea', 'a treia', 'ultima',
            'asta', 'aceasta', 'acestea', 'cea', 'cel',
            'mai mult', 'detalii', 'info', 'informatii',
            'spune-mi despre', 'vreau sa stiu'
        ]
        return any(pattern in message.lower() for pattern in followup_patterns)

    def user_wants_products(self, user_message):
        """Detect if user is asking for products or just info"""
        message_lower = user_message.lower()

        # FAQ keywords = user NU vrea produse (EXPANDED LIST)
        faq_keywords = [
            # Livrare
            'livrare', 'livreaza', 'transport', 'curier', 'colet',
            'cat timp', 'cand ajunge', 'cand primesc', 'durata',

            # Costuri
            'cost', 'cat costa', 'pret livrare', 'taxa',

            # Plata
            'plata', 'platesc', 'card', 'ramburs', 'transfer',

            # Retur & Schimb
            'retur', 'returnare', 'returna', 'returnez',
            'schimb', 'schimba', 'inlocuire',
            'cum fac', 'cum pot', 'pot sa',

            # Contact & Info
            'contact', 'email', 'telefon', 'program', 'orar',
            'cum comand', 'cum plasez', 'cum cumpar',

            # Sizing & Details
            'marime', 'size', 'masura', 'ghid marimi',
            'material', 'compozitie', 'cum se spala',

            # Generale
            'politica', 'conditii', 'termeni'
        ]

        # Check if it's a FAQ question (STRICT MATCH)
        for keyword in faq_keywords:
            if keyword in message_lower:
                return False  # User wants INFO, not products

        # Product keywords = user WANTS products
        product_keywords = [
            'rochie', 'rochii', 'compleu', 'compleuri',
            'camasa', 'camasi', 'pantalon', 'pantaloni',
            'blugi', 'dress', 'vreau', 'caut', 'arată-mi', 'arata',
            'recomanda', 'sugera', 'propune'
        ]

        # Check if asking for products
        for keyword in product_keywords:
            if keyword in message_lower:
                return True  # User wants PRODUCTS

        # Default: if unclear, assume general question
        return False

    def get_response(self, user_message, session_id=None, user_ip=None, user_agent=None):
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"📩 Chat request: {user_message[:50]}...")

        try:
            # 🎯 OPTIMIZATION 1: Rate Limiting (Strategy 6)
            if not self.check_rate_limit(session_id):
                return {
                    "response": "⏳ Prea multe mesaje! Te rog așteaptă puțin.",
                    "status": "rate_limited",
                    "session_id": session_id
                }

            # 🎯 OPTIMIZATION 2: FAQ Cache (Strategy 2) - Check FIRST!
            cached_response = self.check_faq_cache(user_message)
            if cached_response:
                db.save_conversation(
                    session_id, user_message, cached_response, user_ip, user_agent, True)

                return {
                    "response": cached_response,
                    "products": [],
                    "status": "success",
                    "session_id": session_id,
                    "cached": True
                }

            # 🎯 ORDER TRACKING: Check if user is asking about order
            order_id = self.extract_order_number(user_message)
            if order_id:
                logger.info(f"📦 Order tracking request for order #{order_id}")

                # Fetch order from Extended API
                order_data = extended_api.get_order_status(order_id)

                if order_data:
                    # Format elegant response
                    order_response = self.format_order_response(order_data)

                    db.save_conversation(
                        session_id, user_message, order_response, user_ip, user_agent, True)

                    return {
                        "response": order_response,
                        "products": [],
                        "status": "success",
                        "session_id": session_id,
                        "order_tracking": True
                    }
                else:
                    # Order not found
                    error_response = f"""Nu am găsit comanda #{order_id}.

Te rog verifică:
- Numărul comenzii este corect
- Comanda a fost plasată pe ejolie.ro

Pentru asistență: 0757 10 51 51 | contact@ejolie.ro"""

                    db.save_conversation(
                        session_id, user_message, error_response, user_ip, user_agent, True)

                    return {
                        "response": error_response,
                        "products": [],
                        "status": "success",
                        "session_id": session_id
                    }

            # 🎯 OPTIMIZATION 3: Conversation Memory (Strategy 7)
            if self.is_followup_question(user_message):
                cached = self.conversation_cache.get(session_id, {})
                last_products = cached.get('products', [])

                if last_products:
                    # Simple response without GPT call
                    response_text = "Pentru mai multe detalii despre produse, click pe 'Vezi Produs' în carousel!"

                    db.save_conversation(
                        session_id, user_message, response_text, user_ip, user_agent, True)

                    return {
                        "response": response_text,
                        "products": [],
                        "status": "success",
                        "session_id": session_id,
                        "cached": True
                    }

            # Detect category
            category = self.detect_category(user_message)
            logger.info(f"📂 Detected category: {category}")

            # Search products
            # 🎯 Detect if searching for specific model (don't deduplicate colors)
            specific_model_keywords = [
                'frances', 'adela', 'melisa', 'samira', 'clarisse',
                'jesica', 'inessa', 'mara', 'lara', 'sofia'
                # Add more model names as needed
            ]

            search_for_specific_model = any(
                model in user_message.lower()
                for model in specific_model_keywords
            )

            # Search products (with or without deduplication)
            products = self.search_products_in_stock(
                user_message,
                limit=10,
                category=category,
                # Don't deduplicate for specific models
                deduplicate=(not search_for_specific_model)
            )

            # 🎯 OPTIMIZATION 4: Short Product Context (Strategy 3 & 4)
            if products:
                product_summary = f"Am găsit {len(products)} produse relevante în categoria {category}."
            else:
                product_summary = "Nu am găsit produse care să corespundă."

            # 🎯 OPTIMIZATION 5: SHORT System Prompt (Strategy 3)
            system_prompt = f"""Ești Maria, asistent virtual ejolie.ro.

Vindem: rochii, compleuri, cămăși, pantaloni.

REGULI:
- Pentru recomandări: răspuns SCURT (max 10 cuvinte)
- Pentru FAQ: răspuns direct
- Produsele apar în carousel automat

INFO:
- Livrare: 19 lei (gratuit >200 lei), 1-2 zile
- Retur: 14 zile
- Email: contact@ejolie.ro

{product_summary}
"""

            logger.info("🔄 Calling GPT-4o-mini...")

            # 🎯 OPTIMIZATION 6: GPT-4o-mini + Reduced tokens (Strategy 1 & 5)
            response = openai.chat.completions.create(
                model="gpt-4o-mini",  # ← 15x CHEAPER than GPT-4o!
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=150,  # ← Reduced from 500!
                temperature=0.5,
                timeout=15
            )

            bot_response = response.choices[0].message.content
            logger.info(f"✅ GPT response received")

            # Prepare products for frontend
            products_for_frontend = []
            for product in products:
                if len(product) >= 6:
                    products_for_frontend.append({
                        "name": product[0],
                        "price": f"{product[1]:.2f} RON",
                        "description": product[2][:150] + "..." if len(product[2]) > 150 else product[2],
                        "stock": product[3],
                        "link": product[4],
                        "image": product[5]
                    })

            # 🎯 SHORT RESPONSE: Override ONLY if user wants products
            if products_for_frontend and len(products_for_frontend) > 0:
                if self.user_wants_products(user_message):
                    bot_response = self.get_contextual_message(
                        user_message, category)
                    logger.info(f"✂️ Short response applied: {bot_response}")
                else:
                    # User asked info question but we found products - use GPT response
                    logger.info(
                        f"ℹ️ Info question detected, using GPT response")

            # 🎯 OPTIMIZATION: Cache products for follow-ups
            self.conversation_cache[session_id] = {
                'products': products,
                'timestamp': datetime.now(),
                'category': category
            }

            # Save to database
            db.save_conversation(
                session_id, user_message, bot_response, user_ip, user_agent, True
            )

            return {
                "response": bot_response,
                "products": products_for_frontend,
                "status": "success",
                "session_id": session_id
            }

        except openai.RateLimitError as e:
            logger.warning(f"⚠️ OpenAI rate limit: {e}")
            db.save_conversation(
                session_id, user_message, "Rate limit", user_ip, user_agent, False
            )
            return {
                "response": "⏳ Prea multe cereri. Te rog așteaptă câteva secunde.",
                "status": "rate_limited",
                "session_id": session_id
            }

        except openai.AuthenticationError as e:
            logger.error(f"❌ OpenAI Auth error: {e}")
            db.save_conversation(
                session_id, user_message, "Auth failed", user_ip, user_agent, False
            )
            return {
                "response": "❌ Eroare de autentificare. Verifică OPENAI_API_KEY.",
                "status": "auth_error",
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"❌ GPT error: {type(e).__name__}: {e}")
            db.save_conversation(
                session_id, user_message, f"Error: {str(e)}", user_ip, user_agent, False
            )
            return {
                "response": "⚠️ Eroare temporară. Te rog încearcă din nou.",
                "status": "error",
                "session_id": session_id
            }


# ✅ Bot instance
bot = ChatBot()
