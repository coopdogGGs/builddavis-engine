"""Probe what blocks exist at the water tower coords."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from rcon_cmd import rcon

import os; from dotenv import load_dotenv; load_dotenv()
HOST, PORT, PW = 'localhost', 25575, os.environ['RCON_PASS']

# Check centroid (789, 2213) and all 4 leg positions
positions = [
    (789, 2213, "centroid"),
    (787, 2211, "leg-SW"),
    (791, 2211, "leg-SE"),
    (787, 2215, "leg-NW"),
    (791, 2215, "leg-NE"),
]

blocks_to_test = [
    'air', 'iron_block', 'polished_andesite', 'stone', 'grass_block',
    'dirt', 'oak_planks', 'oak_log', 'cobblestone', 'gravel',
    'sand', 'water', 'bricks', 'smooth_stone', 'andesite',
]

for label_x, label_z, label in positions:
    print(f"\n--- {label} (X={label_x}, Z={label_z}) ---")
    for y in [48, 49, 50, 51, 52, 55, 60, 65, 69]:
        cmds = [f"execute if block {label_x} {y} {label_z} minecraft:{b}" for b in blocks_to_test]
        results = rcon(HOST, PORT, PW, cmds)
        for cmd, resp in results.items():
            if 'passed' in resp.lower():
                block = cmd.split("minecraft:")[-1]
                print(f"  Y={y}: {block}")
                break
        else:
            print(f"  Y={y}: (unknown — not in test list)")
