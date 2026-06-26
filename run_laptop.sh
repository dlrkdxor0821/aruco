#!/usr/bin/env bash
# 노트북(laptop)에서 실행 — ArUco 검출 "서버".
# Pi가 보낸 카메라 프레임을 받아 마커를 검출하고 결과를 되돌려준다.
#
# 사용법:
#   ./run_laptop.sh              # 기본 포트 9000, DICT_4X4_50
#   ./run_laptop.sh 9000 DICT_5X5_100
#
# 실행 후 출력되는 이 노트북의 IP를 Pi 쪽 run_pi.sh 에 넣어준다.
set -e
cd "$(dirname "$0")"

PORT="${1:-9000}"
DICT="${2:-DICT_4X4_50}"

echo "================ ArUco 검출 서버 (laptop) ================"
echo "이 노트북 IP 후보:"
# 라즈베리파이에서 접속할 때 쓸 IP 목록
(hostname -I 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || ip -4 addr show 2>/dev/null | grep -oP 'inet \K[0-9.]+') | tr ' ' '\n' | grep -v '^127\.' | sed 's/^/   /'
echo "→ Pi에서:  ./run_pi.sh <위 IP 중 하나>"
echo "포트=$PORT  사전=$DICT"
echo "=========================================================="

exec python3 aruco_server.py --port "$PORT" --dict "$DICT"
