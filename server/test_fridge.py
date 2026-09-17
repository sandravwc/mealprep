from fridge import adds, removes, parse_seen, same, CONTAINER
assert same('Milch', 'H-Milch') and not same('Ei', 'Eiersalat') and same('Feta', 'feta')
seen, hint = parse_seen('```json [{"name":"Milch","category":"dairy"},{"name":"Gurke","category":"nope"},{"name":""},{"name":"milch"}]```')
assert hint == ''
assert parse_seen('{"hinweis": "unscharf", "items": [{"name": "Brot"}]}') == ([{'name': 'Brot', 'category': 'other'}], 'unscharf')
assert [s['name'] for s in seen] == ['Milch', 'Gurke'] and seen[1]['category'] == 'other'
inv = [{'id': 'a', 'name': 'H-Milch', 'category': 'dairy'}, {'id': 'b', 'name': 'Feta', 'category': 'dairy'}, {'id': 'c', 'name': 'Reis', 'category': 'pantry'}]
assert [p['name'] for p in adds(seen, inv)] == ['Gurke']
assert [p['name'] for p in adds([{'name': 'Glas Gurken', 'category': 'other'}, {'name': 'Gurken', 'category': 'other'}], [])] == ['Glas Gurken']
props, misses = removes(['Milch', 'Gurke'], inv, {'b': 1})
assert [p['name'] for p in props] == ['Feta'] and misses == {'b': 2}, (props, misses)  # Reis pantry never, Milch seen -> reset
print('ok')
for junk in ['Kleine blaue Dose', 'Jar with contents', 'Glas mit Inhalt', 'Verpacktes Lebensmittel', 'Alufolie']:
    assert CONTAINER.match(junk), junk
for ok in ['Dosentomaten', 'Glas Gurken', 'Flasche Olivenöl', 'Brot', 'Sahnig']:
    assert not CONTAINER.match(ok), ok
print('ok2')
