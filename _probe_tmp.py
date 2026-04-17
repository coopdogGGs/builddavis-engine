import sys; sys.path.insert(0, 'Code')
from rcon_cmd import rcon

import os; from dotenv import load_dotenv; load_dotenv()
HOST, PORT, PW = 'localhost', 25575, os.environ['RCON_PASS']

blocks_to_test = [
    'air', 'smooth_stone', 'stone_bricks', 'sandstone', 'smooth_sandstone',
    'light_gray_concrete', 'white_concrete', 'gray_concrete', 'polished_andesite',
    'oak_planks', 'glass', 'glass_pane', 'grass_block', 'dirt', 'bricks',
    'stone', 'andesite', 'tuff', 'calcite',
]

print('=== EAST RETAIL BUILDING (unaffected, X=1720-1730) ===')
for (x, y, z) in [(1720, 49, 5200), (1720, 50, 5200), (1720, 52, 5200), 
                   (1725, 52, 5200), (1730, 52, 5200), (1720, 57, 5200),
                   (1720, 49, 5210), (1725, 49, 5210)]:
    cmds = ['execute if block {} {} {} minecraft:{}'.format(x,y,z,b) for b in blocks_to_test]
    results = rcon(HOST, PORT, PW, cmds)
    found = [cmd.split('minecraft:')[-1] for cmd,r in results.items() if 'passed' in r.lower()]
    print('  ({},{},{}): {}'.format(x,y,z, found[0] if found else 'air'))

print()
print('=== NORTH BUILDINGS (across 2nd St, Z=5170-5190) ===')
for (x, y, z) in [(1700, 49, 5180), (1700, 52, 5180), (1710, 52, 5175),
                   (1720, 52, 5175), (1680, 52, 5180)]:
    cmds = ['execute if block {} {} {} minecraft:{}'.format(x,y,z,b) for b in blocks_to_test]
    results = rcon(HOST, PORT, PW, cmds)
    found = [cmd.split('minecraft:')[-1] for cmd,r in results.items() if 'passed' in r.lower()]
    print('  ({},{},{}): {}'.format(x,y,z, found[0] if found else 'air'))

print()
print('=== Y LEVEL CHECK at theater center (figure out ground) ===')
for y in [44, 45, 46, 47, 48, 49, 50, 51]:
    cmds = ['execute if block 1688 {} 5205 minecraft:{}'.format(y,b) for b in blocks_to_test]
    results = rcon(HOST, PORT, PW, cmds)
    found = [cmd.split('minecraft:')[-1] for cmd,r in results.items() if 'passed' in r.lower()]
    print('  Y={} (1688,{},5205): {}'.format(y,y, found[0] if found else 'air'))
