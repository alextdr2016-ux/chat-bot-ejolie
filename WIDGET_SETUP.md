# 🎯 Setup Widget Chatbot - FĂRĂ LOGIN

## ✅ Modificări Efectuate

### 1. Ruta `/widget` - FĂRĂ LOGIN
- ✅ Nu cere autentificare
- ✅ Accesibilă public la: `https://app.fabrex.org/widget`
- ✅ Logging adăugat pentru debugging

### 2. API `/api/chat` - FĂRĂ LOGIN
- ✅ Nu cere autentificare
- ✅ Accesibil public pentru widget
- ✅ Rate limiting: 30 request-uri/minut

### 3. CORS Configuration
- ✅ Permite request-uri din:
  - `https://ejolie.ro`
  - `https://www.ejolie.ro`
  - `https://app.fabrex.org`

### 4. Security Headers (Talisman)
- ✅ `frame-ancestors` permite iframe din `ejolie.ro`
- ✅ `connect-src` permite API calls
- ✅ `SAMEORIGIN` pentru frame-options

---

## 🚀 Testare Widget

### Test 1: Acces Direct
```bash
# Deschide în browser:
https://app.fabrex.org/widget
```

**Așteptat:** Widget-ul se încarcă FĂRĂ să ceară login

---

### Test 2: Test API Chat
```bash
curl -X POST https://app.fabrex.org/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "test",
    "session_id": "test_session_123"
  }'
```

**Așteptat:** Primești răspuns JSON fără eroare 401/403

---

## 📦 Integrare în GTM (Google Tag Manager)

### Cod Iframe pentru GTM

**Tag HTML Custom:**

```html
<!-- Widget Chatbot Ejolie - FĂRĂ LOGIN -->
<iframe
  src="https://app.fabrex.org/widget"
  width="400"
  height="600"
  frameborder="0"
  allow="clipboard-write"
  style="position: fixed; bottom: 20px; right: 20px; border: none; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 9999;"
  title="Ejolie Chat Assistant"
></iframe>
```

### Configurare GTM:

1. **Mergi la GTM Dashboard**
2. **Tags → New → Tag Configuration**
3. **Alege "Custom HTML"**
4. **Lipește codul iframe de mai sus**
5. **Triggering: All Pages** (sau pagini specifice)
6. **Salvează și Publică**

---

## 🔧 Troubleshooting

### ❌ Problema: Widget cere login

**Verificări:**

1. **Check logs server-side:**
   ```bash
   tail -f logs/app.log
   ```
   Caută: "Widget accessed from..."

2. **Verifică dacă alte middleware-uri forțează autentificare**

3. **Test fără GTM:**
   - Deschide direct: `https://app.fabrex.org/widget`
   - Dacă funcționează → problema e în GTM
   - Dacă nu funcționează → problema e în server

### ❌ Problema: CORS Error în Console

**Simptom:**
```
Access to fetch at 'https://app.fabrex.org/api/chat' from origin 'https://ejolie.ro' has been blocked by CORS policy
```

**Soluție:**
- Verifică că `https://ejolie.ro` e în lista CORS (linia 41-49 din main.py)
- Restart server după modificări CORS

### ❌ Problema: Iframe nu se încarcă

**Simptom:** Iframe gol sau "Refused to display"

**Verificări:**

1. **Check CSP headers în browser DevTools:**
   - Network tab → click pe request
   - Verifică Response Headers
   - Caută: `Content-Security-Policy`

2. **Verifică `X-Frame-Options`:**
   - Dacă vezi `DENY` → problema e în Talisman config

**Soluție:** Asigură-te că liniile 56-66 din main.py sunt corect configurate.

---

## 📊 Monitoring

### Verifică că widgetul funcționează:

```bash
# Check health endpoint
curl https://app.fabrex.org/health

# Should return:
{
  "status": "healthy",
  "products_loaded": 1234,
  "scheduler_running": true
}
```

### Verifică logs în timp real:

```bash
# Linux/Mac
tail -f logs/app.log | grep "Widget"

# Windows PowerShell
Get-Content -Path "logs/app.log" -Wait -Tail 50 | Select-String "Widget"
```

---

## ✅ Checklist Final

- [ ] `/widget` se încarcă direct în browser fără login
- [ ] `/api/chat` acceptă POST requests fără autentificare
- [ ] Iframe-ul se încarcă în GTM pe ejolie.ro
- [ ] Chat-ul trimite și primește mesaje
- [ ] Nu apar erori CORS în console
- [ ] Produsele se încarcă și se afișează în carousel

---

## 🔗 Link-uri Utile

- Widget direct: https://app.fabrex.org/widget
- Health check: https://app.fabrex.org/health
- Admin panel: https://app.fabrex.org/admin (cere login)

---

## 🆘 Dacă încă nu funcționează

**Restart complet server:**

```bash
# Stop server
pkill -f "python.*main.py"

# Start server
python main.py
```

**Clear browser cache + cookies:**
- Chrome: Ctrl+Shift+Del → Clear all from ejolie.ro and app.fabrex.org

**Test în Incognito mode** pentru a exclude probleme de sesiune cached.
