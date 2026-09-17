from suggest import parse, build_prompt
assert parse('bla [{"title":"Shakshuka","text":"x","uses":["Eier","Tomaten"]},{"title":""}] ok') == [{'title': 'Shakshuka', 'text': 'x', 'uses': ['Eier', 'Tomaten']}]
p = build_prompt([{'name': 'Eier', 'qty': 10, 'unit': 'Stück', 'expires': '2026-10-01'}], [{'title': 'Pasta', 'time': '2026-09-15 17:00', 'made': True}], '2026-09-17', 'kein Koriander')
assert 'kein Koriander' in p and 'Herbst' in p and 'Pasta' in p and 'Eier (10 Stück' in p
print('ok')
