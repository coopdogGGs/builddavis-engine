"""Minimal RCON client. Usage: python rcon_cmd.py "command1" "command2" ..."""
import socket, struct, sys, time

def rcon(host, port, pw, cmds):
    """Send commands via RCON and return a dict of {cmd: response_body}."""
    responses = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect((host, port))
    # Login
    pkt = struct.pack('<ii', 0, 3) + pw.encode() + b'\x00\x00'
    s.send(struct.pack('<i', len(pkt)) + pkt)
    s.recv(4096)
    for i, cmd in enumerate(cmds):
        pkt = struct.pack('<ii', i+1, 2) + cmd.encode() + b'\x00\x00'
        s.send(struct.pack('<i', len(pkt)) + pkt)
        time.sleep(0.5)
        resp = s.recv(4096)
        body = resp[12:-2].decode('utf-8', errors='replace')
        print(f'[{cmd}] => {body}')
        responses[cmd] = body
    s.close()
    return responses

if __name__ == '__main__':
    rcon('127.0.0.1', 25575, 'REDACTED_RCON_PASS', sys.argv[1:])
