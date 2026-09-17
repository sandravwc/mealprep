from fridge import diff, parse_seen, same
assert same('Milch', 'H-Milch') and not same('Ei', 'Eiersalat') and same('Feta', 'feta')
seen = parse_seen('```json [{"name":"Milch","category":"dairy"},{"name":"Gurke","category":"nope"},{"name":""}]```')
assert [s['name'] for s in seen] == ['Milch', 'Gurke'] and seen[1]['category'] == 'other'
inv = [{'id': 'a', 'name': 'H-Milch', 'category': 'dairy'}, {'id': 'b', 'name': 'Feta', 'category': 'dairy'}, {'id': 'c', 'name': 'Reis', 'category': 'pantry'}]
props, misses = diff(seen, inv, {'b': 1})
assert [(p['kind'], p['name']) for p in props] == [('add', 'Gurke'), ('remove', 'Feta')], props
assert misses == {'b': 2}  # Reis is pantry, never proposed; Milch seen, counter reset
assert diff([], inv, {'b': 1}) == ([], {'b': 1})
print('ok')
