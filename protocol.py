"""UDP framing for sending JPEG frames and receiving detection results.

pinky_perception/perception/common/protocol.py 와 동일한 방식.
laptop(서버) 쪽이 pinky_perception 저장소 없이도 독립 실행되도록 같이 둔 사본이다.

JPEG 한 프레임은 보통 UDP 한 패킷(max 65507B)보다 크므로 청크로 쪼갠다. 각 패킷 헤더:

    frame_id (uint32) | total_chunks (uint16) | chunk_idx (uint16) | crc32 (uint32)

뒤에 청크 페이로드가 붙는다. 두 가지 견고성 보장:
  1. CRC32 체크섬 — 페이로드가 손상되면 그 패킷을 버린다.
  2. 오래된 프레임 폐기 — 항상 가장 최신 frame_id 만 재조립, 늦게 온 옛 패킷은 무시.
"""
import struct
import zlib

HEADER_FMT = "!IHHI"  # frame_id, total_chunks, chunk_idx, crc32(payload)
HEADER_SIZE = struct.calcsize(HEADER_FMT)
DEFAULT_CHUNK = 1400  # MTU(~1500) 아래로 유지해 IP 단편화를 피한다

RESULT_FMT = "!I"  # 검출 회신 앞에 붙는 frame_id
RESULT_SIZE = struct.calcsize(RESULT_FMT)


def encode_frame(frame_id, payload, chunk_size=DEFAULT_CHUNK):
    """`payload`(JPEG 바이트)를 sendto() 할 수 있는 datagram 리스트로 쪼갠다."""
    chunks = [payload[i:i + chunk_size] for i in range(0, len(payload), chunk_size)] or [b""]
    total = len(chunks)
    fid = frame_id & 0xFFFFFFFF
    out = []
    for idx, chunk in enumerate(chunks):
        crc = zlib.crc32(chunk) & 0xFFFFFFFF
        out.append(struct.pack(HEADER_FMT, fid, total, idx, crc) + chunk)
    return out


class Reassembler:
    """프레임이 완성될 때까지 청크를 모은다. datagram 마다 push() 호출.

    항상 본 것 중 가장 최신 frame_id 를 추적하고, 더 오래된 미완성 프레임은 버린다.
    """

    def __init__(self):
        self._buf = {}
        self._latest = -1

    def push(self, datagram):
        """최신 프레임이 완성되면 (frame_id, payload) 반환, 아니면 None.

        CRC 불일치나 오래된 패킷이면 그 패킷을 버리고 None 반환.
        """
        if len(datagram) < HEADER_SIZE:
            return None
        frame_id, total, idx, crc = struct.unpack(HEADER_FMT, datagram[:HEADER_SIZE])
        payload = datagram[HEADER_SIZE:]

        if (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
            return None  # 1) 손상 패킷 폐기

        # 2) 오래된 프레임 폐기
        if frame_id < self._latest:
            return None
        if frame_id > self._latest:
            self._latest = frame_id
            for old in [k for k in self._buf if k < frame_id]:
                del self._buf[old]

        slot = self._buf.setdefault(frame_id, {})
        slot[idx] = payload
        if len(slot) >= total:
            data = b"".join(slot[i] for i in range(total) if i in slot)
            del self._buf[frame_id]
            return frame_id, data
        return None


def encode_result(frame_id, json_bytes):
    return struct.pack(RESULT_FMT, frame_id & 0xFFFFFFFF) + json_bytes


def decode_result(datagram):
    frame_id = struct.unpack(RESULT_FMT, datagram[:RESULT_SIZE])[0]
    return frame_id, datagram[RESULT_SIZE:]
