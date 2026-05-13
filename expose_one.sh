#!/bin/bash
# Expose a single agent via ngrok
# Usage: ./expose_one.sh hibbett
#        ./expose_one.sh nto
#        ./expose_one.sh shiseido

AGENT=$1

case "$AGENT" in
  hibbett)
    PORT=8501
    NAME="Hibbett Shopper Agent"
    ;;
  nto)
    PORT=8502
    NAME="NTO Trail Advisor"
    ;;
  shiseido)
    PORT=8503
    NAME="Shiseido Beauty Advisor"
    ;;
  *)
    echo "Usage: $0 {hibbett|nto|shiseido}"
    exit 1
    ;;
esac

echo "🌐 Exposing $NAME on port $PORT..."
echo ""
echo "Public URL will be displayed below:"
echo "Press Ctrl+C to stop the tunnel"
echo ""

ngrok http $PORT --authtoken=3DeE2e93eC3RQ85dUnBMXOjP4VE_2gKqMDcYEmhFqD27ZabBT
