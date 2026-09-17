from config import clean, DEFAULTS
c = clean({'categories': {'Meat': [3, 0], 'bad': ['x', 1], 'neg': [-1, 0]}, 'tags': {'a': 'A', '': 'no', 'b': ' '}})
assert c == {'categories': {'meat': [3, 0], 'other': DEFAULTS['categories']['other']}, 'tags': {'a': 'A'}}, c
print('ok')
