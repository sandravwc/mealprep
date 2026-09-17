from janitor import clean_inventory, clean_suggestions
inv = [{'name': 'Eier', 'receipt': 'a', 'expires': '2026-12-01', 'category': 'eggs'},
       {'name': 'Eier', 'receipt': 'a', 'expires': '2026-12-01', 'category': 'eggs'},
       {'name': 'Milch', 'receipt': 'a', 'expires': '2026-01-01', 'category': 'dairy'},
       {'name': 'Trinkhalm', 'receipt': 'a', 'expires': '2026-12-01', 'category': 'zzz'},
       {'name': 'Reis', 'receipt': 'b', 'expires': '2027-01-01', 'category': 'zzz'}]
out, dropped = clean_inventory(inv, {'trinkhalm': ''}, '2026-09-10')
assert [i['name'] for i in out] == ['Eier', 'Reis'] and out[1]['category'] == 'other', (out, dropped)
assert len(dropped) == 3
assert clean_suggestions([{'id': 'x', 'title': 'a'}, {'id': 'x', 'title': 'a'}, {'title': 'no id'}]) == ([{'id': 'x', 'title': 'a'}], 2)
print('ok')
