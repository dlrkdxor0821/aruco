#!/usr/bin/env bash
# 라즈베리파이(Pi)에서 실행 — 카메라 캡처 + ArUco 직접 검출 + "정보만" 노트북 전송.
# 이미지를 보내지 않고 추출한 마커 정보(id/거리/방향)만 보내므로 대역폭이 작다.
# 시각화는 노트북의 run_laptop.sh(뷰어)에서 한다.
#
# 사용법:
#   ./run_pi.sh <laptop-ip>                  # 기본 포트 9000, 마커 5cm, csi, rotate 180
#   MARKER=0.08 ./run_pi.sh 192.168.0.25     # 마커 한 변 8cm
#   CALIB=calib.npz MARKER=0.08 ./run_pi.sh 192.168.0.25   # 정확 거리
#   LOG=1 ./run_pi.sh 192.168.0.25           # 터미널에도 프레임마다 값 출력
set -e
cd "$(dirname "$0")"

HOST="${1:-}"
PORT="${2:-9000}"
DICT="${DICT:-DICT_6X6_250}"
MARKER="${MARKER:-0.05}"     # 마커 한 변 실제 길이(m). 인쇄 크기로 맞출 것!
HFOV="${HFOV:-54}"
ROTATE="${ROTATE:-180}"
SOURCE="${SOURCE:-csi}"

if [ -z "$HOST" ]; then
  echo "사용법: ./run_pi.sh <laptop-ip> [port]"
  echo "  예) MARKER=0.08 ./run_pi.sh 192.168.0.25"
  exit 1
fi

ARGS=(--host "$HOST" --port "$PORT" --dict "$DICT"
      --marker-size "$MARKER" --hfov "$HFOV"
      --source "$SOURCE" --rotate "$ROTATE")
[ -n "$CALIB" ] && ARGS+=(--calib "$CALIB")
[ -n "$LOG" ] && ARGS+=(--log)

echo "============== ArUco 검출+송신 (Pi) =============="
echo "검출 주체=Pi → laptop $HOST:$PORT 로 정보 전송"
echo "마커=${MARKER}m  사전=$DICT  보정=${CALIB:-없음(화각 ${HFOV}° 근사)}"
echo "================================================="

exec python3 pi_detect_send.py "${ARGS[@]}"
