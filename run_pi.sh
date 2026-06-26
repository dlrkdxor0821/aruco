#!/usr/bin/env bash
# 라즈베리파이(Pi)에서 실행 — 카메라 캡처 + UDP 송신 + 브라우저 프리뷰 "클라이언트".
# CSI 카메라로 프레임을 잡아 노트북(서버)으로 보내고, 받은 검출 결과를 그려
# http://<Pi-IP>:8090/ 로 스트리밍한다.
#
# 사용법:
#   ./run_pi.sh <laptop-ip>                  # 기본값: 포트 9000, csi, rotate 180
#   ./run_pi.sh 192.168.0.10 9000 DICT_6X6_250
#
# 서버(laptop)의 --dict 와 여기 사전 이름을 동일하게 맞춰야 한다.
set -e
cd "$(dirname "$0")"

HOST="${1:-}"
PORT="${2:-9000}"
DICT="${3:-DICT_6X6_250}"   # 참고용 — 실제 검출 사전은 서버(run_laptop.sh)에서 정한다
ROTATE="${ROTATE:-180}"
SOURCE="${SOURCE:-csi}"

if [ -z "$HOST" ]; then
  echo "사용법: ./run_pi.sh <laptop-ip> [port] [dict]"
  echo "  예) ./run_pi.sh 192.168.0.10"
  exit 1
fi

PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "============== ArUco 클라이언트 (Pi) =============="
echo "서버(laptop): $HOST:$PORT   카메라=$SOURCE   rotate=$ROTATE"
echo "프리뷰 보기:  http://${PI_IP:-<이-Pi-IP>}:8090/"
echo "(서버 run_laptop.sh 의 --dict 가 $DICT 와 같은지 확인)"
echo "=================================================="

exec python3 aruco_client.py \
  --host "$HOST" --udp-port "$PORT" \
  --source "$SOURCE" --rotate "$ROTATE"
