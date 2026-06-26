#!/usr/bin/env bash
# 노트북(laptop)에서 실행 — Pi 가 보낸 영상+값을 받아 브라우저로 보여주는 "뷰어".
# 검출은 Pi 가 하고, 여기서는 받은 실제 영상에 마커 오버레이를 그려 MJPEG 로 스트리밍.
#
# 사용법:
#   ./run_laptop.sh              # UDP 9000 수신, 브라우저 8090
#   ./run_laptop.sh 9000 8090    # UDP포트 브라우저포트
#
# 실행 후 출력되는 이 노트북의 IP를 Pi 쪽 run_pi.sh 에 넣어주고,
# 브라우저에서 http://<노트북-IP>:8090/ 를 연다.
set -e
cd "$(dirname "$0")"

UDP_PORT="${1:-9000}"
WEB_PORT="${2:-8090}"

echo "================ ArUco 뷰어 (laptop) ================"
echo "이 노트북 IP 후보 (Pi 가 이 IP 로 보냄 / 브라우저도 이 IP):"
(hostname -I 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || ip -4 addr show 2>/dev/null | grep -oP 'inet \K[0-9.]+') | tr ' ' '\n' | grep -v '^127\.' | sed 's/^/   /'
echo "→ Pi 에서:  MARKER=0.08 ./run_pi.sh <위 IP 중 하나>"
echo "→ 브라우저: http://<위 IP>:${WEB_PORT}/   (또는 http://localhost:${WEB_PORT}/)"
echo "UDP 수신=${UDP_PORT}  브라우저=${WEB_PORT}"
echo "====================================================="

exec python3 laptop_visualize.py --udp-port "$UDP_PORT" --port "$WEB_PORT"
