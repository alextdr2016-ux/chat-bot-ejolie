import pandas as pd

data = {
    'Nume': ['Rochie Roșie', 'Rochie Albastră', 'Rochie Verde'],
    'Pret vanzare (cu promotie)': [250, 450, 300],
    'Stoc': ['În Stoc', 'În Stoc', 'În Stoc'],
    'Descriere':
    ['Rochie roșie frumoasă', 'Rochie albastră nuntă', 'Rochie verde festivă'],
    'Link produs':
    ['https://ejolie.ro/1', 'https://ejolie.ro/2', 'https://ejolie.ro/3']
}

df = pd.DataFrame(data)
df.to_csv('products.csv', index=False, encoding='utf-8')
print('CSV creat!')
