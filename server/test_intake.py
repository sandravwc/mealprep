from intake import parse_items
raw = '```json\n[{"name":"Ba Banane","qty":"0,8","unit":"kg","category":"produce"},{"name":"","qty":1},{"name":"H-Milch","qty":2,"unit":"1L","category":"milk"}]\n```'
items = parse_items(raw, {'ba banane': 'Banane'})
assert [i['name'] for i in items] == ['Banane', 'H-Milch'], items
assert items[0]['qty'] == 1.0 and items[0]['category'] == 'produce'   # "0,8" unparsable -> 1
assert items[1]['qty'] == 2.0 and items[1]['category'] == 'other'     # unknown category -> other
print('ok')
assert parse_items('Sorry, this image shows a cat, not a receipt.', {}) == []
print('ok2')
