#!/usr/bin/env bash
# 라즈베리파이 단독 ArUco 인식 — 노트북/네트워크 없이 Pi가 직접 검출.
# WiFi 패킷 손실로 인한 끊김이 없다.
#
# 사용법:
#   ./run_pi_solo.sh                 # 마커 5cm 기본, 화각 근사
#   MARKER=0.08 ./run_pi_solo.sh     # 마커 한 변 8cm
#   CALIB=calib.npz MARKER=0.08 ./run_pi_solo.sh   # 정확 거리
#   LOG=1 ./run_pi_solo.sh           # 터미널에도 프레임마다 값 출력
set -e
cd "$(dirname "$0")"

MARKER="${MARKER:-0.05}"
DICT="${DICT:-DICT_6X6_250}"
HFOV="${HFOV:-54}"

ARGS=(--dict "$DICT" --marker-size "$MARKER" --hfov "$HFOV")
[ -n "$CALIB" ] && ARGS+=(--calib "$CALIB")
[ -n "$LOG" ] && ARGS+=(--log)

PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "========== ArUco 인식 (Pi 단독) =========="
echo "검출 주체=Pi   마커=${MARKER}m   보정=${CALIB:-없음(화각 ${HFOV}° 근사)}"
echo "프리뷰: http://${PI_IP:-<이-Pi-IP>}:8090/"
echo "=========================================="

exec python3 detect_pi.py "${ARGS[@]}"
