from config import clean, DEFAULTS
c = clean({'categories': {'Meat': [3, 0], 'bad': ['x', 1], 'neg': [-1, 0]}, 'tags': {'a': 'A', '': 'no', 'b': ' '}})
assert c == {'categories': {'meat': [3, 0], 'other': DEFAULTS['categories']['other']}, 'tags': {'a': 'A'}, 'meals': DEFAULTS['meals']}, c
assert clean({'meals': [{'name': 'Frühstück', 'time': '07:30'}, {'name': 'x', 'time': '25:00'}]})['meals'] == [{'name': 'Frühstück', 'time': '07:30'}]
print('ok')
