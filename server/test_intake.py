from intake import parse_items
raw = '```json\n[{"name":"Ba Banane","qty":"0,8","unit":"kg","category":"produce"},{"name":"","qty":1},{"name":"H-Milch","qty":2,"unit":"1L","category":"milk"}]\n```'
items = parse_items(raw, {'ba banane': 'Banane'})
assert parse_items('[{"raw":"GQ EIER XL BODEN","name":"GQ Eier"}]', {'gq eier xl boden': 'Eier XL Bodenhaltung'})[0]['name'] == 'Eier XL Bodenhaltung'
assert [i['name'] for i in items] == ['Banane', 'H-Milch'], items
assert items[0]['qty'] == 1.0 and items[0]['category'] == 'produce'   # "0,8" unparsable -> 1
assert items[1]['qty'] == 2.0 and items[1]['category'] == 'other'     # unknown category -> other
print('ok')
assert parse_items('Sorry, this image shows a cat, not a receipt.', {}) == []
print('ok2')
assert parse_items('[{"raw":"TRINKHALM","name":"Trinkhalm"},{"name":"Eier"}]', {'trinkhalm': ''}) == [{'raw': '', 'name': 'Eier', 'qty': 1.0, 'unit': 'Stück', 'category': 'other'}]
print('ok3')
