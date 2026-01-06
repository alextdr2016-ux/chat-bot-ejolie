import pandas as pd

df = pd.read_excel('export_produse_chat_bot.xlsx')
df.to_csv('products.csv', index=False, encoding='utf-8')
print('✅ CSV creat!')
