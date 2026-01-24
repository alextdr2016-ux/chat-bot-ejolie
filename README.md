# 🤖 Ejolie Chatbot - AI-Powered Customer Support

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11-green)
![Flask](https://img.shields.io/badge/flask-2.3-orange)
![OpenAI](https://img.shields.io/badge/openai-gpt--4-blueviolet)

**Chatbot intelligent cu AI (GPT-4) pentru magazinul online de rochii - ejolie.ro**

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Admin Panel Guide](#admin-panel-guide)
- [CSV Format](#csv-format)
- [API Endpoints](#api-endpoints)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Future Improvements](#future-improvements)

---

## 🎯 Overview

**Ejolie Chatbot** este un asistent virtual AI-powered pentru magazinul online de rochii de eveniment **ejolie.ro**.

Chatbot-ul ajută clienții să:

- 🔍 Caute rochii după descriere, culoare, preț
- 💰 Filtreze produse după preț
- 📦 Verifice disponibilitatea stocului
- 📦 Primească informații despre livrare, retur, contact
- 💬 Obțină răspunsuri la întrebări frecvente

---

## ✨ Features Complète

### 🎯 Core Functionality

✅ **Chat Interface Floating Widget**

- Buton flotant în colțul dreapta jos
- Modal responsive (desktop/mobil)
- Integrare via Google Tag Manager
- Dark mode compatible

✅ **AI-Powered Responses**

- GPT-4 integration
- Natural language processing
- Context-aware answers
- Multi-language support (Romanian)

✅ **Product Management**

- 480+ produse în catalogul live
- Filtrare după: nume, culoare, preț, stoc
- Search inteligent cu scoring
- In-stock status real-time

✅ **Stock Management**

- Verificare disponibilitate produse
- Status visual: ✅ În stoc / ❌ Epuizat
- Filter căutări doar din stoc
- Daily sync din CSV

✅ **Logistics Information**

- Info livrare (timp, cost)
- Politică retur detaliată
- Contact direct (email, telefon)
- Shipping gratuit >200 lei

✅ **FAQ System**

- Răspunsuri la întrebări frecvente
- Integrare în context GPT
- Editable din admin panel

✅ **Analytics & Tracking**

- Logging toate conversațiile
- Timestamp pentru fiecare mesaj
- User message + Bot response
- Data export

✅ **Admin Panel**

- 6 tab-uri de gestionare
- Logistics config (contact, shipping, retur)
- Occasions management (Nuntă, Botez, etc)
- FAQ editor
- Custom Rules
- Products CSV upload/sync
- Analytics real-time

---

## 🛠️ Tech Stack

### **Backend**

- **Language:** Python 3.11
- **Framework:** Flask 2.3
- **AI:** OpenAI GPT-4 API
- **Database:** JSON (conversations.json)
- **Data Processing:** Pandas
- **Logging:** Python logging

### **Frontend**

- **HTML5, CSS3, JavaScript (Vanilla)**
- **Responsive Design**
- **Google Tag Manager Integration**
- **No external dependencies (except bootstrap styling)**

### **Deployment**

- **Platform:** Railway.app
- **Database:** File-based JSON
- **Environment:** Ubuntu 24, Python 3.11

### **Tools**

- Git & GitHub
- VSCode
- Terminal/CLI

---

## 📁 Project Structure

```
ejolie-chatbot/
│
├── chatbot.py              # Core chatbot logic (AI, search, stock)
├── main.py                 # Flask app, routes, uploads
├── requirements.txt        # Python dependencies
├── Procfile                # Railway deployment config
│
├── templates/
│   ├── index.html          # Chat frontend
│   └── admin.html          # Admin panel (6 tabs)
│
├── static/
│   ├── chat.css            # Chat styling
│   ├── chat.js             # Chat JavaScript
│   └── index.html          # Chat frontend
│
├── products.csv            # Product catalog (480+ items)
├── config.json             # Settings (logistics, FAQ, etc)
├── conversations.json      # Chat history
│
├── README.md               # This file
└── .env                    # Environment variables (IGNORED)
```

---

## 🚀 Installation

### **Prerequisites**

- Python 3.9+
- Git
- OpenAI API Key
- CSV cu produse (format specific)

### **Step 1: Clone Repository**

```bash
git clone https://github.com/yourusername/ejolie-chatbot.git
cd ejolie-chatbot
```

### **Step 2: Create Virtual Environment**

```bash
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### **Step 3: Install Dependencies**

```bash
pip install -r requirements.txt
```

### **Step 4: Create .env File**

```bash
# .env
OPENAI_API_KEY=sk-proj-your-api-key-here
ADMIN_PASSWORD=admin123
FLASK_ENV=production
```

### **Step 5: Add Initial Files**

```bash
# Create empty files
touch config.json conversations.json

# Add sample config.json
echo '{"logistics": {}, "occasions": [], "faq": [], "custom_rules": []}' > config.json
```

### **Step 6: Run Locally**

```bash
python main.py

# Visit http://localhost:3000
```

---

## ⚙️ Configuration

### **config.json - Main Settings**

```json
{
  "logistics": {
    "contact": {
      "email": "contact@ejolie.ro",
      "phone": "+40 XXX XXX XXX"
    },
    "shipping": {
      "days": "3-5 zile",
      "cost_standard": "25 lei"
    },
    "return_policy": "Retur 30 zile..."
  },
  "occasions": ["Nuntă", "Botez", "Logodnă", "Cununia civila"],
  "faq": [
    {
      "question": "Cat costa transportul?",
      "answer": "Transportul costa 25 lei pentru comenzi sub 200 lei. Pentru comenzi peste 200 lei, transportul este GRATUIT."
    }
  ],
  "custom_rules": []
}
```

### **Environment Variables**

```bash
OPENAI_API_KEY=sk-proj-xxx          # OpenAI API key (REQUIRED)
ADMIN_PASSWORD=admin123             # Admin panel password
FLASK_ENV=production                # Flask environment
PORT=3000                           # Server port (default 3000)
```

---

## 💬 Usage

### **For End Users**

1. **Open ejolie.ro**
2. **Click floating button** (bottom-right corner)
3. **Type your question:**
   ```
   "Aveti rochie rosie sub 300 de lei?"
   "Cand vine livrarea?"
   "Cand se face retur?"
   "Rochii pentru nunta"
   ```
4. **Get instant AI response** with product recommendations

### **For Admin Users**

1. **Access admin panel:** `ejolie.ro/admin`
2. **Login:** Password required (admin123)
3. **6 Management Tabs:**
   - 📦 **Logistics:** Edit contact, shipping, return policy
   - 🎭 **Occasions:** Add wedding, christening occasions
   - 💬 **FAQ:** Add frequent questions & answers
   - ⚙️ **Custom Rules:** Add custom response rules
   - 📦 **Products:** Upload/sync CSV with products
   - 📊 **Analytics:** View customer conversations

---

## 📊 Admin Panel Guide

### **Tab 1: 📦 Logistics**

```
Settings:
├── Contact Email: contact@ejolie.ro
├── Contact Phone: +40 XXX XXX XXX
├── Shipping Days: 3-5 zile
├── Shipping Cost: 25 lei (FREE >200 lei)
└── Return Policy: 30 zile retur...
```

**Action:** Edit → Enter password → Save

---

### **Tab 2: 🎭 Occasions**

```
Add custom occasions for recommendations:
- Nuntă
- Botez
- Logodnă
- Cununia civila
- Gala
- etc.
```

**Action:** Add new → Save

---

### **Tab 3: 💬 FAQ**

```
Add Q&A pairs:
Q: "Cum se face plata?"
A: "Acceptam: Card credit, PayPal, Transfer bancar, Plata cash la livrare"
```

**Action:** Add new Q&A → Save

---

### **Tab 4: ⚙️ Custom Rules**

```
Advanced routing:
Title: Retur
Type: logistics_info
Content: "Poti face retur 30 zile..."
```

**Action:** Add new → Save

---

### **Tab 5: 📦 Products - CSV Upload**

```
SYNC MODE: Upload new CSV → Auto-replace old products

Required CSV format:
┌────────────────────────────────────────────────┐
│ Nume,Pret vanzare (cu promotie),Descriere,stoc│
│ Rochie Rosie,250,Din tafta cu paiete,15       │
│ Rochie Albastra,320,Din matase,0              │
└────────────────────────────────────────────────┘

Features:
✅ Auto-detect encoding (UTF-8 → latin-1 fallback)
✅ Validate columns
✅ Stock management
✅ Real-time sync
✅ Check Status button (verify load count)
```

**Action:** Select CSV → Enter password → Click "Sync Products" → Check Status

---

### **Tab 6: 📊 Analytics**

```
View all customer conversations:
├── Timestamp
├── User Message
└── Bot Response

Export: Data shown with timestamps
Filter: By password access
```

**Action:** Click "Reîncarcă" → View conversation history

---

## 📋 CSV Format

### **Required Structure**

```csv
Nume,Pret vanzare (cu promotie),Descriere,stoc
Rochie Rosie Eleganta,250,Rochie din tafta cu paiete,15
Rochie Albastra Sofisticata,320,Rochie din matase naturala,0
Rochie Galbena Usoara,180,Rochie din voal ușor,5
```

### **Column Details**

| Column                     | Type   | Required | Example                      |
| -------------------------- | ------ | -------- | ---------------------------- |
| Nume                       | String | ✅ YES   | "Rochie Rosie Eleganta"      |
| Pret vanzare (cu promotie) | Number | ✅ YES   | 250                          |
| Descriere                  | String | ✅ YES   | "Rochie din tafta cu paiete" |
| stoc                       | Number | ✅ YES   | 15                           |

### **Encoding**

- ✅ **UTF-8** (preferred)
- ✅ **Latin-1** (fallback, auto-detected)

---

## 🔌 API Endpoints

### **Public Endpoints**

#### **1. Chat - Send Message**

```
POST /api/chat
Content-Type: application/json

Request:
{
  "message": "Aveti rochie rosie sub 300 de lei?"
}

Response:
{
  "response": "Da, avem rochii roz disponibile sub 300 lei...",
  "status": "success"
}
```

#### **2. Health Check**

```
GET /health

Response:
{
  "status": "ok",
  "timestamp": "2026-01-07T12:00:00",
  "products_loaded": 480,
  "total_conversations": 45,
  "version": "1.0.0"
}
```

#### **3. Get Config**

```
GET /api/config

Response:
{
  "logistics": {...},
  "occasions": [...],
  "faq": [...],
  "custom_rules": [...]
}
```

---

### **Protected Endpoints (Admin)**

#### **4. Save Config**

```
POST /api/admin/save-config
Headers:
  X-Admin-Password: admin123
Content-Type: application/json

Request:
{
  "config": {
    "logistics": {...},
    "occasions": [...],
    "faq": [...]
  }
}
```

#### **5. Upload Products**

```
POST /api/admin/upload-products
Headers:
  X-Admin-Password: admin123
Body: multipart/form-data (CSV file)

Response:
{
  "status": "success",
  "message": "Synced! 480 products loaded, 0 removed",
  "products_count": 480
}
```

#### **6. Get Conversations (Analytics)**

```
GET /api/conversations?password=admin123

Response:
[
  {
    "timestamp": "2026-01-07T12:00:00",
    "user_message": "Rochie rosie?",
    "bot_response": "Da, avem..."
  }
]
```

#### **7. Check Products Status**

```
GET /api/admin/check-products?password=admin123

Response:
{
  "file_exists": true,
  "file_size": 282429,
  "bot_products_count": 480,
  "bot_products_sample": [...]
}
```

---

## 🚀 Deployment

### **Deploy to Railway.app (Current)**

1. **Connect GitHub Repository**

   ```
   Railway Dashboard → New Project → GitHub Repo
   ```

2. **Set Environment Variables**

   ```
   OPENAI_API_KEY=sk-proj-xxx
   ADMIN_PASSWORD=admin123
   ```

3. **Auto-Deploy on Git Push**

   ```bash
   git push origin main
   # Railway auto-rebuilds & deploys
   ```

4. **Live URL**
   ```
   https://chat-bot-ejolie-production.up.railway.app
   ```

### **Google Tag Manager Integration**

1. **Go to GTM Dashboard**
2. **Create Custom HTML Tag**
3. **Paste code from `/gtm-tag.js`**
4. **Trigger: All Pages**
5. **Publish**

---

## 🔍 Troubleshooting

### **Problem: "Bot products loaded: 0"**

**Cause:** CSV encoding or columns mismatch

**Solution:**

```bash
# Check CSV columns
head -1 products.csv

# Should see:
# Nume,Pret vanzare (cu promotie),Descriere,stoc

# If not, re-export as CSV with correct columns
```

---

### **Problem: Chat Not Responding**

**Cause:** OpenAI API key issue or network error

**Solution:**

```bash
# 1. Verify API key in .env
echo $OPENAI_API_API

# 2. Check Railway logs
railway logs

# 3. Verify API quota on OpenAI dashboard
# https://platform.openai.com/account/billing
```

---

### **Problem: "undefined" Error in Admin**

**Cause:** Response message not formatted correctly

**Solution:**

```javascript
// In admin.html, check uploadProducts() function
successMsg.innerHTML = `✅ ${data.message || "Products synced!"}`;
```

---

### **Problem: Products Not Searching Correctly**

**Cause:** Product names have typos or special characters

**Solution:**

```python
# In chatbot.py, search_products() uses:
# 1. Full name match (score +3)
# 2. Partial matches in description (score +1)
# 3. Word-by-word search (score +2/-1)

# Try searching with fewer keywords
# Example: "rochie rosie" instead of "rochie very special rosie 2024"
```

---

## 📈 Future Improvements

### **Phase 1 (Next 1-2 months)**

- [ ] Multi-tenant SaaS architecture
- [ ] Email integration (send to support@ejolie.ro)
- [ ] WhatsApp business integration
- [ ] SMS notifications
- [ ] Advanced analytics (sentiment analysis)

### **Phase 2 (Months 3-4)**

- [ ] Database migration (PostgreSQL)
- [ ] User accounts (save favorites)
- [ ] Wishlist feature
- [ ] Push notifications
- [ ] Mobile app (React Native)

### **Phase 3 (Months 5-6)**

- [ ] Payment integration (Stripe)
- [ ] Order tracking
- [ ] Return management
- [ ] Inventory sync (auto-update from ecommerce)
- [ ] Multilingual support

---

## 📚 Documentation Files

- **[Architecture](./docs/ARCHITECTURE.md)** - System design
- **[API Reference](./docs/API.md)** - Complete endpoint docs
- **[Deployment Guide](./docs/DEPLOYMENT.md)** - Railway, Docker, AWS
- **[Troubleshooting](./docs/TROUBLESHOOTING.md)** - Common issues & fixes

---

## 📞 Support & Contact

**For Bot Issues:**

```
Email: contact@ejolie.ro
Phone: +40 XXX XXX XXX
Hours: 9 AM - 6 PM (Mon-Fri)
```

**For Development Support:**

```
GitHub: github.com/yourusername/ejolie-chatbot
Email: dev@ejolie.ro
```

---

## 📄 License

MIT License - Feel free to use for personal/commercial projects

---

## 👨‍💻 Contributors

- Alexandru - Full Stack Developer
- OpenAI GPT-4 - AI Engine

---

## 🙏 Acknowledgments

- OpenAI for GPT-4 API
- Railway.app for hosting
- Ejolie.ro for the amazing use case
- Flask community for the framework

---

## 📊 Statistics

| Metric               | Value        |
| -------------------- | ------------ |
| Products             | 480+         |
| Languages            | 1 (Romanian) |
| Response Time        | <2s          |
| Uptime               | 99.9%        |
| Conversations Logged | 45+          |
| Admin Users          | 1            |

---

## 🎯 Roadmap

```
Q1 2026: ✅ Core chatbot (DONE)
         📦 Stock management (DONE)
         📊 Analytics (DONE)
         🔧 Admin panel (DONE)

Q2 2026: 🔄 Multi-tenant SaaS
         💳 Payment integration
         📲 Mobile app

Q3 2026: 🤖 ML improvements
         🌍 Multi-language
         📈 Advanced analytics
```

---

## 🚀 Getting Started

```bash
# 1. Clone
git clone https://github.com/yourusername/ejolie-chatbot.git

# 2. Setup
cd ejolie-chatbot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your API keys

# 4. Run
python main.py

# 5. Visit
# Chat: http://localhost:3000
# Admin: http://localhost:3000/admin
```

---

**Last Updated:** January 7, 2026

**Version:** 1.0.0

**Status:** ✅ Production Ready
# Force redeploy 01/20/2026 19:23:37
