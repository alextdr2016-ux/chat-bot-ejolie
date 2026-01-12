# 🔐 Login Setup - Email și Parolă

Autentificarea cu **Magic Link** a fost eliminată. Acum aplicația folosește doar **Email + Parolă**.

## 📋 Ce s-a schimbat

### ✅ Eliminat:
- Magic Link authentication (email + link în email)
- Rutele `/api/auth/request-login` și `/auth/magic`
- Tab-urile din pagina de login

### ✅ Adăugat:
- Autentificare cu **Email + Parolă**
- Hash-uri sigure pentru parole (pbkdf2:sha256)
- Coloana `password_hash` în tabela `users`

## 🚀 Setup Inițial

### 1. Migrare bază de date (dacă există deja)

Dacă ai deja o bază de date cu utilizatori, rulează scriptul de migrare:

```bash
python migrate_db.py
```

Acest script adaugă coloana `password_hash` la tabela `users`.

### 2. Creează utilizator admin

Folosește scriptul pentru a crea un utilizator admin cu parolă:

```bash
python create_admin.py <email> <password>
```

**Exemplu:**
```bash
python create_admin.py alextdr2016@gmail.com MySecurePassword123
```

### 3. (Alternativ) Script interactiv

Poți folosi scriptul interactiv care te întreabă email și parolă:

```bash
python set_admin_password.py
```

## 🔑 Credențiale Admin Create

**Email:** alextdr2016@gmail.com
**Parolă:** Admin123!

⚠️ **IMPORTANT:** Schimbă această parolă după primul login în producție!

## 🌐 Utilizare

1. Pornește serverul:
```bash
python main.py
```

2. Accesează pagina de login:
```
http://localhost:5000/login
```

3. Autentifică-te cu:
   - **Email:** alextdr2016@gmail.com
   - **Parolă:** Admin123!

4. Vei fi redirecționat către `/admin`

## 🔒 Securitate

- Parolele sunt hash-uite folosind **pbkdf2:sha256** (Werkzeug)
- Sesiunile durează **7 zile**
- Rate limiting: **5 încercări pe minut**
- HTTPS obligatoriu în producție (Talisman)

## 📝 Creare utilizatori noi

Pentru a crea utilizatori noi cu parolă:

```bash
python create_admin.py email@example.com NewPassword123
```

Sau programatic în Python:

```python
from werkzeug.security import generate_password_hash
from database import db

# Creează utilizator
user = db.create_user_if_missing(email="user@example.com", role="client")

# Setează parolă
password_hash = generate_password_hash("password", method='pbkdf2:sha256')
db.set_user_password("user@example.com", password_hash)
```

## 🛠️ Troubleshooting

### Eroare: "no such column: password_hash"
Rulează scriptul de migrare:
```bash
python migrate_db.py
```

### Eroare: "Cont fără parolă configurată"
Setează o parolă pentru utilizator:
```bash
python create_admin.py <email> <password>
```

### Nu pot să mă autentific
Verifică că:
1. Email-ul este corect (lowercase)
2. Parola este corectă
3. Utilizatorul are `password_hash` setat în baza de date

## 📚 Fișiere importante

- `main.py` - Endpoint-uri de autentificare
- `database.py` - Funcții pentru parole (set_user_password, verify_user_password)
- `templates/login.html` - Pagina de login
- `migrate_db.py` - Script de migrare
- `create_admin.py` - Script pentru creare admin
- `set_admin_password.py` - Script interactiv

## 🔄 Rollback (dacă e nevoie)

Dacă vrei să revii la Magic Link, restaurează fișierele din commit-ul anterior.
