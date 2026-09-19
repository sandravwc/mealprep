from dyndns import valid
assert valid('87.122.205.5') and not valid('192.168.1.106') and not valid('10.0.0.1') and not valid('nope') and not valid('')
print('ok')
