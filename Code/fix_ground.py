"""
fix_ground.py - Patches data_processing.rs to place bedrock at ground_level-15.
BuildDavis ADR-004: exactly 15 blocks to bedrock from surface.
"""
path = 'REDACTED_PATH/builddavis-engine/src/data_processing.rs'

with open(path, 'r') as f:
    src = f.read()

# Fix 1: Replace fillground to fill only from bedrock_y+1 to ground_y-1
# instead of filling from MIN_Y+1 to ground_y-3
old_fill = '''                    if args.fillground {
                        editor.fill_column_absolute(
                            STONE,
                            x,
                            z,
                            MIN_Y + 1,
                            ground_y - 3,
                            true, // skip_existing: don't overwrite blocks placed by element processing
                        );
                    }
                    // Generate a bedrock level at MIN_Y
                    editor.set_block_absolute(BEDROCK, x, MIN_Y, z, None, Some(&[BEDROCK]));'''

new_fill = '''                    // BuildDavis ADR-004: bedrock at ground_level-15, stone above
                    // This gives exactly 15 blocks to dig before hitting bedrock
                    let bedrock_y = ground_y - 15;
                    editor.set_block_absolute(BEDROCK, x, bedrock_y, z, None, Some(&[BEDROCK]));
                    if args.fillground {
                        editor.fill_column_absolute(
                            STONE,
                            x,
                            z,
                            bedrock_y + 1,
                            ground_y - 1,
                            true, // skip_existing: don't overwrite blocks placed by element processing
                        );
                    }'''

if old_fill in src:
    src = src.replace(old_fill, new_fill)
    with open(path, 'w') as f:
        f.write(src)
    print('PATCHED OK - bedrock now at ground_level-15')
else:
    print('NOT FOUND - checking nearby text')
    idx = src.find('fillground')
    print(repr(src[max(0,idx-50):idx+300]))
