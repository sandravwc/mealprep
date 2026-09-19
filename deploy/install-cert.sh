#!/data/data/com.termux/files/usr/bin/sh
# acme.sh reloadcmd: haproxy wants one pem with chain + key
cat $HOME/mealprep/tls/fullchain.pem $HOME/mealprep/tls/key.pem > $HOME/mealprep/tls/haproxy.pem
chmod 600 $HOME/mealprep/tls/haproxy.pem
SVDIR=$PREFIX/var/service sv restart haproxy
