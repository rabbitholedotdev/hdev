"""Cliente WebSocket mínimo (RFC 6455) sobre socket Unix. Só stdlib."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import socket
import struct

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_TEXT, OP_CLOSE, OP_PING, OP_PONG = 0x1, 0x8, 0x9, 0xA


class WsError(RuntimeError):
    pass


def _mask_key():
    return secrets.token_bytes(4)


def encode_frame(payload, opcode=OP_TEXT, masked=True):
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    n = len(payload)
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))
    mask_bit = 0x80 if masked else 0
    if n < 126:
        header.append(mask_bit | n)
    elif n < 65536:
        header.append(mask_bit | 126)
        header.extend(struct.pack("!H", n))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack("!Q", n))
    if masked:
        key = _mask_key()
        header.extend(key)
        payload = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
    return bytes(header) + payload


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise WsError("conexão fechada")
        buf.extend(chunk)
    return bytes(buf)


def decode_frame(sock):
    b1, b2 = _recv_exact(sock, 2)
    opcode = b1 & 0x0F
    masked = bool(b2 & 0x80)
    n = b2 & 0x7F
    if n == 126:
        n = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif n == 127:
        n = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    key = _recv_exact(sock, 4) if masked else b""
    payload = _recv_exact(sock, n)
    if masked:
        payload = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
    return opcode, payload


def handshake(sock, path="/ws", host="localhost"):
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    req = (
        "GET %s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Sec-WebSocket-Key: %s\r\n"
        "\r\n"
    ) % (path, host, key)
    sock.sendall(req.encode("ascii"))
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise WsError("handshake incompleto")
        data += chunk
    head, rest = data.split(b"\r\n\r\n", 1)
    status = head.split(b"\r\n", 1)[0]
    if b"101" not in status:
        raise WsError("upgrade recusado: %s" % status.decode("ascii", "replace")[:200])
    headers = {}
    for line in head.split(b"\r\n")[1:]:
        if b":" in line:
            k, v = line.split(b":", 1)
            headers[k.strip().lower()] = v.strip()
    expect = base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest())
    got = headers.get(b"sec-websocket-accept", b"")
    if got != expect:
        raise WsError("Sec-WebSocket-Accept inválido")
    return rest


def connect(path, timeout=30, ws_path="/ws"):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(path)
    leftover = handshake(sock, path=ws_path)
    return sock, leftover


def request(path, message, timeout=30, ws_path="/ws", sock=None):
    """Envia um pedido JSON {id, op, ...} e devolve a resposta {t:'resposta', id, ok, ...}.
    Ignora eventos no meio. Nunca imprime o conteúdo além do que o chamador fizer."""
    own = sock is None
    leftover = b""
    if own:
        sock, leftover = connect(path, timeout=timeout, ws_path=ws_path)
    try:
        if leftover:
            pass  # 101 body should be empty
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        sock.sendall(encode_frame(payload, opcode=OP_TEXT, masked=True))
        want = message.get("id")
        while True:
            opcode, data = decode_frame(sock)
            if opcode == OP_PING:
                sock.sendall(encode_frame(data, opcode=OP_PONG, masked=True))
                continue
            if opcode == OP_CLOSE:
                raise WsError("servidor fechou o WebSocket")
            if opcode != OP_TEXT:
                continue
            try:
                obj = json.loads(data.decode("utf-8"))
            except ValueError as e:
                raise WsError("resposta não é JSON") from e
            if not isinstance(obj, dict):
                continue
            if obj.get("t") == "resposta" and obj.get("id") == want:
                return obj
            # eventos (t=evento, estado, ...) são ignorados
    finally:
        if own:
            try:
                sock.sendall(encode_frame(b"", opcode=OP_CLOSE, masked=True))
            except OSError:
                pass
            sock.close()
