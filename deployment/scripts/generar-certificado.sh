#!/bin/sh
# Genera el certificado HTTPS propio de la institución (sin Internet ni autoridades externas).
# Uso: sh deployment/scripts/generar-certificado.sh <IP del servidor> [nombre]
#   p. ej.: sh deployment/scripts/generar-certificado.sh 192.168.1.10 atrapanieblas.local
# Crea deployment/certs/servidor.crt y servidor.key (la clave no se versiona). Válido 5 años.
# Cada equipo debe aceptar el certificado una vez (o instalar servidor.crt como confiable).
set -eu
IP="${1:?Indique la IP del servidor en la red local}"
NAME="${2:-atrapanieblas.local}"
DIR="$(dirname "$0")/../certs"
mkdir -p "$DIR"
umask 077
openssl req -x509 -newkey rsa:2048 -nodes -days 1825 \
  -keyout "$DIR/servidor.key" -out "$DIR/servidor.crt" \
  -subj "/O=CEA Ildefonso de las Munecas/CN=$NAME" \
  -addext "subjectAltName=IP:$IP,DNS:$NAME,DNS:localhost,IP:127.0.0.1"
chmod 644 "$DIR/servidor.crt"
echo "Certificado creado en $DIR (servidor.crt). Huella SHA-256:"
openssl x509 -in "$DIR/servidor.crt" -noout -fingerprint -sha256
