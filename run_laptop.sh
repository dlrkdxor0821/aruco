#!/usr/bin/env bash
# 노트북(laptop)에서 실행 — Pi 가 보낸 ArUco "정보"를 받아 시각화하는 "뷰어".
# 검출은 Pi 가 하고, 여기서는 받은 마커 정보를 캔버스에 그려 보여준다(창).
#
# 사용법:
#   ./run_laptop.sh              # UDP 9000 수신, 화면 창으로 표시 (q 종료)
#   ./run_laptop.sh 9000
#
# 실행 후 출력되는 이 노트북의 IP를 Pi 쪽 run_pi.sh 에 넣어준다.
set -e
cd "$(dirname "$0")"

PORT="${1:-9000}"

echo "================ ArUco 뷰어 (laptop) ================"
echo "이 노트북 IP 후보 (Pi 에서 이 IP 로 보냄):"
(hostname -I 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || ip -4 addr show 2>/dev/null | grep -oP 'inet \K[0-9.]+') | tr ' ' '\n' | grep -v '^127\.' | sed 's/^/   /'
echo "→ Pi 에서:  ./run_pi.sh <위 IP 중 하나>"
echo "수신 포트=$PORT   (검출/마커크기/보정은 Pi 쪽 run_pi.sh 에서 설정)"
echo "====================================================="

exec python3 laptop_visualize.py --port "$PORT"
