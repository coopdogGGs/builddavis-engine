"""Check the terrain around the water tower's current position to find a clear spot."""
import os, struct

# Current water tower position
WT_X, WT_Z = 2515, 6096
FOOTPRINT = 33

# We need to find a spot nearby that doesn't overlap roads
# The tower is 33x33. Let's check offsets.
# From the screenshot, the road runs along the south/west edge.
# If we shift the tower east (+X) or north (-Z) we might clear it.

# Real-world: the water tower sits at lat 38.535, lon -121.749 
# which is on the UC Davis campus, near the Segundo Dining Commons area
# It's surrounded by open land/fields, not on a road.

# Let's check what the bbox math says for the real water tower location
# Bbox: S=38.530, W=-121.785, N=38.575, E=-121.720
# NW corner = MC origin (0,0), X grows east (increasing lon), Z grows south (decreasing lat)

lat, lon = 38.535, -121.749
N, S = 38.575, 38.530
W, E = -121.785, -121.720

import math
lat_scale = 111000  # m/deg
lon_scale = 111000 * math.cos(math.radians(38.55))

world_width = (E - W) * lon_scale   # meters east-west
world_depth = (N - S) * lat_scale   # meters north-south

mc_x = (lon - W) / (E - W) * world_width
mc_z = (N - lat) / (N - S) * world_depth

print(f"Water tower real-world: lat={lat}, lon={lon}")
print(f"Bbox math MC coords: X={mc_x:.0f}, Z={mc_z:.0f}")
print(f"Current config coords: X={WT_X}, Z={WT_Z}")
print(f"Difference: dX={mc_x - WT_X:.0f}, dZ={mc_z - WT_Z:.0f}")
print()
print(f"Suggested: try placing at X={int(mc_x)}, Z={int(mc_z)} (bbox estimate)")
print(f"Or shift current position east by ~15 blocks: X={WT_X + 15}, Z={WT_Z}")
