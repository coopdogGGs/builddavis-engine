import os

home = os.path.expanduser('~')
p = os.path.join(home, 'builddavis-engine', 'src', 'world_editor', 'java.rs')

f = open(p).read()

old = 'chunk.set_block(x, -62, z, GRASS_BLOCK);'
new = 'chunk.set_block(x, 0, z, BEDROCK);'

old2 = 'use crate::block_definitions::GRASS_BLOCK;'
new2 = 'use crate::block_definitions::{GRASS_BLOCK, BEDROCK};'

if old in f:
    f = f.replace(old, new)
    print('Patched: base chunk Y=-62 grass -> Y=0 bedrock')
else:
    print('NOT FOUND: grass block line')

if old2 in f:
    f = f.replace(old2, new2)
    print('Patched: added BEDROCK import')
else:
    print('NOT FOUND: import line')

open(p, 'w').write(f)
print('Done')
