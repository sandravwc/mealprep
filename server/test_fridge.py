from fridge import adds, removes, parse_seen, same
assert same('Milch', 'H-Milch') and not same('Ei', 'Eiersalat') and same('Feta', 'feta')
seen = parse_seen('```json [{"name":"Milch","category":"dairy"},{"name":"Gurke","category":"nope"},{"name":""}]```')
assert [s['name'] for s in seen] == ['Milch', 'Gurke'] and seen[1]['category'] == 'other'
inv = [{'id': 'a', 'name': 'H-Milch', 'category': 'dairy'}, {'id': 'b', 'name': 'Feta', 'category': 'dairy'}, {'id': 'c', 'name': 'Reis', 'category': 'pantry'}]
assert [p['name'] for p in adds(seen, inv)] == ['Gurke']
props, misses = removes(['Milch', 'Gurke'], inv, {'b': 1})
assert [p['name'] for p in props] == ['Feta'] and misses == {'b': 2}, (props, misses)  # Reis pantry never, Milch seen -> reset
print('ok')
