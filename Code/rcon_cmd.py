"""Minimal RCON client. Usage: python rcon_cmd.py "command1" "command2" ..."""
import os, socket, struct, sys, time

def rcon(host, port, pw, cmds):
    """Send commands via RCON and return a dict of {cmd: response_body}."""
    responses = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    try:
        s.connect((host, port))
        # Login
        pkt = struct.pack('<ii', 0, 3) + pw.encode() + b'\x00\x00'
        s.send(struct.pack('<i', len(pkt)) + pkt)
        login_resp = s.recv(4096)
        # Validate: request ID field; -1 means auth failure
        if len(login_resp) >= 8:
            resp_id = struct.unpack('<i', login_resp[4:8])[0]
            if resp_id == -1:
                raise RuntimeError("RCON authentication failed (bad password?)")
        for i, cmd in enumerate(cmds):
            pkt = struct.pack('<ii', i+1, 2) + cmd.encode() + b'\x00\x00'
            s.send(struct.pack('<i', len(pkt)) + pkt)
            time.sleep(0.05)
            resp = s.recv(4096)
            body = resp[12:-2].decode('utf-8', errors='replace')
            print(f'[{cmd}] => {body}')
            responses[cmd] = body
    finally:
        s.close()
    return responses

if __name__ == '__main__':
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
    rcon(
        os.environ.get('RCON_HOST', '127.0.0.1'),
        int(os.environ.get('RCON_PORT', '25575')),
        os.environ['RCON_PASS'],
        sys.argv[1:],
    )
