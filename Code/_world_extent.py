import os, re, glob

saves = os.path.expandvars(r'%APPDATA%\.minecraft\saves\BuildDavis\region')
xs, zs = [], []
for f in glob.glob(os.path.join(saves, 'r.*.*.mca')):
    m = re.search(r'r\.(-?\d+)\.(-?\d+)\.mca', f)
    if m:
        xs.append(int(m.group(1)))
        zs.append(int(m.group(2)))

print(f"Total region files: {len(xs)}")
print(f"Region X: {min(xs)} to {max(xs)}  =>  Block X: {min(xs)*512} to {(max(xs)+1)*512-1}")
print(f"Region Z: {min(zs)} to {max(zs)}  =>  Block Z: {min(zs)*512} to {(max(zs)+1)*512-1}")
print(f"World approx size: {(max(xs)-min(xs)+1)*512} x {(max(zs)-min(zs)+1)*512} blocks")
