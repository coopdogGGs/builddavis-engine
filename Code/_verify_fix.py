import os

p = os.path.join(os.environ['APPDATA'], '.minecraft', 'saves', 'BuildDavis',
                 'datapacks', 'builddavis', 'data', 'builddavis', 'function',
                 'place_water_tower.mcfunction')
t = open(p).read()
print("iron_chain count:", t.count("iron_chain"))
print("minecraft:chain count:", t.count("minecraft:chain"))
