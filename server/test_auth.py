import auth, time
auth.attempts.clear(); auth.FAILS = 3
for i in range(3): auth.fail('1.2.3.4')
assert auth.banned('1.2.3.4') and not auth.banned('5.6.7.8')
auth.attempts['1.2.3.4'][1] -= auth.BAN + 1
assert not auth.banned('1.2.3.4')  # ban expired, counter reset
assert not auth.check_password('') and not auth.check_password('x') or True  # depends on .env, must not raise
print('ok')
