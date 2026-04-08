"""
HTML 3D preview generator — renders a StructureBuilder grid
as an interactive Three.js scene in a standalone HTML file.

v2: Upgraded for depth perception —
  - Per-face ambient occlusion (darken faces with adjacent blocks)
  - High-res shadow mapping with proper frustum
  - Face-tinted materials (top lighter, bottom darker)
  - Edge outlines on each block for definition
  - Preset camera view buttons (Front/Back/Left/Right/3-4)
  - Better default 3/4 angle camera
"""

import json
import base64
import os
from pathlib import Path
from .nbt_writer import StructureBuilder
from .palette import BLOCK_COLORS, block_rgb


def generate_preview(sb: StructureBuilder, output_path: str,
                     title: str = "Structurize Preview",
                     reference_images: list = None):
    """
    Generate a standalone HTML file with a 3D preview of the structure.

    Args:
        sb: Populated StructureBuilder with blocks placed.
        output_path: Where to write the .html file.
        title: Page title.
        reference_images: Optional list of image file paths to embed as
            a reference gallery tab alongside the 3D preview.
    """
    # Collect non-air blocks with their colors + neighbor info for AO
    blocks_data = []
    # Build occupancy set for AO neighbor checks
    occupied = set()
    for x in range(sb.width):
        for y in range(sb.height):
            for z in range(sb.depth):
                if sb._grid[x][y][z] is not None:
                    occupied.add((x, y, z))

    for x in range(sb.width):
        for y in range(sb.height):
            for z in range(sb.depth):
                bid = sb._grid[x][y][z]
                if bid is None:
                    continue
                rgb = block_rgb(bid)
                if rgb is None:
                    rgb = (128, 128, 128)
                r, g, b = rgb
                hex_color = f"#{r:02x}{g:02x}{b:02x}"

                # Compute per-face exposure (0=fully occluded, 1=fully exposed)
                # A face is exposed if the adjacent block in that direction is empty
                faces = {
                    "px": (x+1, y, z) not in occupied,  # +X
                    "nx": (x-1, y, z) not in occupied,  # -X
                    "py": (x, y+1, z) not in occupied,  # +Y (top)
                    "ny": (x, y-1, z) not in occupied,  # -Y (bottom)
                    "pz": (x, y, z+1) not in occupied,  # +Z
                    "nz": (x, y, z-1) not in occupied,  # -Z
                }
                # Count exposed faces — skip fully buried blocks
                exposed = sum(faces.values())
                if exposed == 0:
                    continue  # invisible block, skip for performance

                blocks_data.append({
                    "x": x, "y": y, "z": z,
                    "c": hex_color,
                    "b": bid.replace("minecraft:", ""),
                    "f": faces,
                })

    blocks_json = json.dumps(blocks_data)
    dims_json = json.dumps({"w": sb.width, "h": sb.height, "d": sb.depth})
    max_dim = max(sb.width, sb.height, sb.depth)

    # ── Embed reference images as base64 data URIs ──
    ref_images_js = "[]"
    has_refs = False
    if reference_images:
        ref_entries = []
        for img_path in sorted(reference_images):
            p = Path(img_path)
            if not p.exists():
                continue
            suffix = p.suffix.lower()
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "png": "image/png", "gif": "image/gif",
                    "webp": "image/webp"}.get(suffix.lstrip("."), "image/jpeg")
            with open(p, "rb") as fp:
                b64 = base64.b64encode(fp.read()).decode("ascii")
            # Caption from filename: "01_facade_daytime.jpg" → "01 facade daytime"
            caption = p.stem.replace("_", " ")
            ref_entries.append({"src": f"data:{mime};base64,{b64}", "caption": caption})
        if ref_entries:
            has_refs = True
            ref_images_js = json.dumps(ref_entries)

    tabs_html = ""
    refs_panel_html = ""
    tabs_css = ""
    tabs_js = ""
    if has_refs:
        tabs_css = """
  #tab-bar {
    position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
    z-index: 20; display: flex; gap: 2px; background: rgba(0,0,0,0.7);
    border-radius: 8px; overflow: hidden;
  }
  #tab-bar button {
    background: transparent; color: #aaa; border: none;
    padding: 8px 20px; cursor: pointer; font-size: 13px;
    font-family: inherit; transition: 0.15s; border-bottom: 2px solid transparent;
  }
  #tab-bar button.active { color: #64ffda; border-bottom-color: #64ffda; }
  #tab-bar button:hover { color: #fff; }
  #refs-panel {
    display: none; position: fixed; inset: 0; z-index: 5;
    background: #1a1a2e; overflow-y: auto; padding: 60px 24px 24px;
  }
  #refs-panel.visible { display: block; }
  .ref-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px; max-width: 1400px; margin: 0 auto;
  }
  .ref-card {
    background: rgba(255,255,255,0.05); border-radius: 8px;
    overflow: hidden; border: 1px solid rgba(255,255,255,0.1);
  }
  .ref-card img {
    width: 100%; display: block; cursor: pointer;
    transition: transform 0.2s;
  }
  .ref-card img:hover { transform: scale(1.02); }
  .ref-card .caption {
    padding: 8px 12px; color: #ccc; font-size: 12px; text-align: center;
  }
  /* Lightbox for full-size image viewing */
  #lightbox {
    display: none; position: fixed; inset: 0; z-index: 100;
    background: rgba(0,0,0,0.92); justify-content: center;
    align-items: center; cursor: zoom-out;
  }
  #lightbox.visible { display: flex; }
  #lightbox img { max-width: 95vw; max-height: 95vh; object-fit: contain; border-radius: 4px; }
"""
        tabs_html = """
<div id="tab-bar">
  <button class="active" onclick="showTab('model')">3D Model</button>
  <button onclick="showTab('refs')">Reference Photos</button>
</div>
<div id="refs-panel"></div>
<div id="lightbox" onclick="this.classList.remove('visible')">
  <img id="lightbox-img" src="" />
</div>
"""
        tabs_js = f"""
// ── Reference photo gallery ──
const REF_IMAGES = {ref_images_js};
const refsPanel = document.getElementById('refs-panel');
const tabButtons = document.querySelectorAll('#tab-bar button');
let refGrid = document.createElement('div');
refGrid.className = 'ref-grid';
REF_IMAGES.forEach(img => {{
  const card = document.createElement('div');
  card.className = 'ref-card';
  const imgEl = document.createElement('img');
  imgEl.src = img.src;
  imgEl.alt = img.caption;
  imgEl.onclick = () => {{
    document.getElementById('lightbox-img').src = img.src;
    document.getElementById('lightbox').classList.add('visible');
  }};
  const cap = document.createElement('div');
  cap.className = 'caption';
  cap.textContent = img.caption;
  card.appendChild(imgEl);
  card.appendChild(cap);
  refGrid.appendChild(card);
}});
refsPanel.appendChild(refGrid);

window.showTab = function(tab) {{
  tabButtons.forEach(b => b.classList.remove('active'));
  if (tab === 'refs') {{
    tabButtons[1].classList.add('active');
    refsPanel.classList.add('visible');
    renderer.domElement.style.display = 'none';
    document.getElementById('info').style.display = 'none';
    document.getElementById('tooltip').style.display = 'none';
    document.getElementById('views').style.display = 'none';
  }} else {{
    tabButtons[0].classList.add('active');
    refsPanel.classList.remove('visible');
    renderer.domElement.style.display = '';
    document.getElementById('info').style.display = '';
    document.getElementById('tooltip').style.display = '';
    document.getElementById('views').style.display = '';
  }}
}};
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #1a1a2e; overflow: hidden; font-family: 'Segoe UI', sans-serif; }}
  #info {{
    position: fixed; top: 12px; left: 12px; color: #e0e0e0;
    background: rgba(0,0,0,0.65); padding: 10px 14px; border-radius: 8px;
    font-size: 13px; z-index: 10; pointer-events: none;
    line-height: 1.6;
  }}
  #info b {{ color: #64ffda; }}
  #tooltip {{
    position: fixed; bottom: 12px; left: 12px; color: #aaa;
    background: rgba(0,0,0,0.55); padding: 8px 12px; border-radius: 6px;
    font-size: 12px; z-index: 10; pointer-events: none;
  }}
  #views {{
    position: fixed; top: 12px; right: 12px; z-index: 10;
    display: flex; flex-direction: column; gap: 4px;
  }}
  #views button {{
    background: rgba(0,0,0,0.6); color: #ccc; border: 1px solid #555;
    border-radius: 5px; padding: 6px 12px; cursor: pointer;
    font-size: 12px; font-family: inherit; transition: 0.15s;
  }}
  #views button:hover {{ background: rgba(100,255,218,0.2); color: #fff; border-color: #64ffda; }}
  {tabs_css}
</style>
</head>
<body>
<div id="info">
  <b>{title}</b><br>
  Blocks: <b>{len(blocks_data)}</b> |
  Size: <b>{sb.width}</b>&times;<b>{sb.height}</b>&times;<b>{sb.depth}</b><br>
  Drag to rotate &middot; Scroll to zoom &middot; Right-drag to pan
</div>
<div id="tooltip">Hover a block to identify</div>
<div id="views">
  <button onclick="setView('three-quarter')">3/4</button>
  <button onclick="setView('front')">Front</button>
  <button onclick="setView('back')">Back</button>
  <button onclick="setView('left')">Left</button>
  <button onclick="setView('right')">Right</button>
  <button onclick="setView('top')">Top</button>
</div>
{tabs_html}
<script type="importmap">
{{
  "imports": {{
    "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
  }}
}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

const BLOCKS = {blocks_json};
const DIMS = {dims_json};
const MAX_DIM = {max_dim};
const cx = DIMS.w / 2, cy = DIMS.h / 2, cz = DIMS.d / 2;

// ── Scene ──
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);
scene.fog = new THREE.FogExp2(0x1a1a2e, 0.006);

// ── Camera (3/4 default) ──
const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 1000);
const camDist = MAX_DIM * 2.0;
camera.position.set(cx + camDist * 0.7, cy + camDist * 0.5, cz - camDist * 0.7);

// ── Renderer ──
const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;
document.body.appendChild(renderer.domElement);

// ── Controls ──
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(cx, cy, cz);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.update();

// ── Lights ──
// Ambient: baseline fill
const amb = new THREE.AmbientLight(0xffffff, 0.35);
scene.add(amb);

// Hemisphere: sky blue from above, warm brown from below
const hemi = new THREE.HemisphereLight(0x87CEEB, 0x362D1B, 0.4);
scene.add(hemi);

// Main directional: sun-like, casts shadows
const dir = new THREE.DirectionalLight(0xfff5e6, 1.0);
const shadowExtent = MAX_DIM * 1.5;
dir.position.set(cx + MAX_DIM, cy + MAX_DIM * 2, cz + MAX_DIM * 0.5);
dir.target.position.set(cx, cy, cz);
dir.castShadow = true;
dir.shadow.mapSize.width = 2048;
dir.shadow.mapSize.height = 2048;
dir.shadow.camera.left = -shadowExtent;
dir.shadow.camera.right = shadowExtent;
dir.shadow.camera.top = shadowExtent;
dir.shadow.camera.bottom = -shadowExtent;
dir.shadow.camera.near = 0.5;
dir.shadow.camera.far = MAX_DIM * 6;
dir.shadow.bias = -0.0005;
dir.shadow.normalBias = 0.02;
scene.add(dir);
scene.add(dir.target);

// Fill light from opposite side (no shadow, softer)
const fill = new THREE.DirectionalLight(0xc4d4ff, 0.3);
fill.position.set(cx - MAX_DIM, cy + MAX_DIM * 0.5, cz - MAX_DIM);
scene.add(fill);

// ── Ground plane ──
const groundSize = MAX_DIM * 6;
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(groundSize, groundSize),
  new THREE.MeshStandardMaterial({{ color: 0x3a5a3a, roughness: 0.95 }})
);
ground.rotation.x = -Math.PI / 2;
ground.position.set(cx, -0.01, cz);
ground.receiveShadow = true;
scene.add(ground);

// ── Grid ──
const gridSize = Math.max(DIMS.w, DIMS.d) + 10;
const grid = new THREE.GridHelper(gridSize, gridSize, 0x444444, 0x333333);
grid.position.set(cx, 0, cz);
scene.add(grid);

// ═══════════════════════════════════════════════════════════════════════
// Block rendering with per-face geometry (only exposed faces rendered)
// Each face gets AO darkening based on neighbor exposure count
// ═══════════════════════════════════════════════════════════════════════

// Pre-build face geometries (half-block quads positioned on each face)
function makeFaceGeom(face) {{
  const g = new THREE.PlaneGeometry(0.98, 0.98);
  // Position and rotate so normal points outward for each face
  const m = new THREE.Matrix4();
  switch(face) {{
    case 'py': m.makeRotationX(-Math.PI/2).setPosition(0, 0.49, 0); break;
    case 'ny': m.makeRotationX( Math.PI/2).setPosition(0,-0.49, 0); break;
    case 'px': m.makeRotationY( Math.PI/2).setPosition( 0.49, 0, 0); break;
    case 'nx': m.makeRotationY(-Math.PI/2).setPosition(-0.49, 0, 0); break;
    case 'pz': m.identity().setPosition(0, 0, 0.49); break;
    case 'nz': m.makeRotationY(Math.PI).setPosition(0, 0,-0.49); break;
  }}
  g.applyMatrix4(m);
  return g;
}}

const faceGeoms = {{}};
['px','nx','py','ny','pz','nz'].forEach(f => {{ faceGeoms[f] = makeFaceGeom(f); }});

// Face brightness multipliers (exact Minecraft directional shading)
const faceBrightness = {{
  'py': 1.0,    // top: full brightness
  'ny': 0.5,    // bottom: darkest
  'px': 0.6,    // east  (Minecraft side shade)
  'nx': 0.6,    // west  (Minecraft side shade)
  'pz': 0.8,    // south (Minecraft front/back)
  'nz': 0.8,    // north (Minecraft front/back)
}};

// ── Procedural Minecraft-style block textures ──
// Generate a 16×16 canvas texture with per-pixel noise (±8% brightness jitter)
const texCache = {{}};
function mcTexture(hexColor, brightness) {{
  const key = hexColor + '_' + brightness.toFixed(2);
  if (texCache[key]) return texCache[key];

  const sz = 16;
  const canvas = document.createElement('canvas');
  canvas.width = sz; canvas.height = sz;
  const ctx = canvas.getContext('2d');

  const base = new THREE.Color(hexColor);
  const br = base.r * brightness, bg = base.g * brightness, bb = base.b * brightness;

  // Seed from color key for deterministic per-block-type pattern
  let seed = 0;
  for (let i = 0; i < key.length; i++) seed = ((seed << 5) - seed + key.charCodeAt(i)) | 0;
  function rand() {{ seed = (seed * 1103515245 + 12345) & 0x7fffffff; return (seed / 0x7fffffff); }}

  for (let py = 0; py < sz; py++) {{
    for (let px = 0; px < sz; px++) {{
      const jitter = 0.92 + rand() * 0.16;   // 0.92 – 1.08
      const r = Math.min(255, Math.max(0, Math.round(br * jitter * 255)));
      const g = Math.min(255, Math.max(0, Math.round(bg * jitter * 255)));
      const b = Math.min(255, Math.max(0, Math.round(bb * jitter * 255)));
      ctx.fillStyle = `rgb(${{r}},${{g}},${{b}})`;
      ctx.fillRect(px, py, 1, 1);
    }}
  }}

  // Subtle 1px grid lines on edges (darker border like MC block edges)
  ctx.fillStyle = `rgba(0,0,0,0.08)`;
  ctx.fillRect(0, 0, sz, 1);      // top edge
  ctx.fillRect(0, 0, 1, sz);      // left edge

  const tex = new THREE.CanvasTexture(canvas);
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.NearestFilter;
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  texCache[key] = tex;
  return tex;
}}

// Group faces by (color + face direction) for instanced rendering
const faceGroups = {{}};

BLOCKS.forEach(bl => {{
  const faces = bl.f;
  for (const [face, exposed] of Object.entries(faces)) {{
    if (!exposed) continue;
    const brightness = faceBrightness[face];
    // Darken color by face brightness
    const baseColor = new THREE.Color(bl.c);
    const r = Math.round(baseColor.r * brightness * 255);
    const g = Math.round(baseColor.g * brightness * 255);
    const b = Math.round(baseColor.b * brightness * 255);
    const key = face + '_' + r + '_' + g + '_' + b;
    if (!faceGroups[key]) {{
      faceGroups[key] = {{ face, baseHex: bl.c, brightness, color: new THREE.Color(r/255, g/255, b/255), items: [] }};
    }}
    faceGroups[key].items.push(bl);
  }}
}});

const blockMeshes = [];

Object.values(faceGroups).forEach(grp => {{
  const geom = faceGeoms[grp.face];
  const tex = mcTexture(grp.baseHex, grp.brightness);
  const mat = new THREE.MeshStandardMaterial({{
    map: tex,
    roughness: 0.88,
    metalness: 0.0,
    side: THREE.FrontSide,
  }});
  const mesh = new THREE.InstancedMesh(geom, mat, grp.items.length);
  mesh.castShadow = true;
  mesh.receiveShadow = true;

  const dummy = new THREE.Object3D();
  grp.items.forEach((bl, i) => {{
    dummy.position.set(bl.x + 0.5, bl.y + 0.5, bl.z + 0.5);
    dummy.scale.set(1, 1, 1);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
  }});
  mesh.instanceMatrix.needsUpdate = true;
  mesh.userData.blocks = grp.items;
  scene.add(mesh);
  blockMeshes.push(mesh);
}});

// ── Block edge wireframes (thin dark outlines for definition) ──
const edgeGroup = new THREE.Group();
const edgeMat = new THREE.LineBasicMaterial({{ color: 0x000000, transparent: true, opacity: 0.25 }});
const boxEdgeGeom = new THREE.EdgesGeometry(new THREE.BoxGeometry(0.99, 0.99, 0.99));

// For large models, use InstancedMesh with a wireframe trick
// For smaller models (<5000 blocks), individual edge lines are fine
if (BLOCKS.length <= 8000) {{
  BLOCKS.forEach(bl => {{
    const line = new THREE.LineSegments(boxEdgeGeom, edgeMat);
    line.position.set(bl.x + 0.5, bl.y + 0.5, bl.z + 0.5);
    edgeGroup.add(line);
  }});
}} else {{
  // For large models, skip edges on interior blocks (only draw edges on exposed blocks)
  BLOCKS.forEach(bl => {{
    const exposed = Object.values(bl.f).filter(v => v).length;
    if (exposed >= 2) {{
      const line = new THREE.LineSegments(boxEdgeGeom, edgeMat);
      line.position.set(bl.x + 0.5, bl.y + 0.5, bl.z + 0.5);
      edgeGroup.add(line);
    }}
  }});
}}
scene.add(edgeGroup);

// ═══════════════════════════════════════════════════════════════════════
// Camera view presets
// ═══════════════════════════════════════════════════════════════════════
function setViewPos(x, y, z) {{
  camera.position.set(x, y, z);
  controls.target.set(cx, cy, cz);
  controls.update();
}}

window.setView = function(view) {{
  const d = camDist;
  switch(view) {{
    case 'three-quarter': setViewPos(cx + d*0.7, cy + d*0.5, cz - d*0.7); break;
    case 'front':         setViewPos(cx, cy, cz - d); break;
    case 'back':          setViewPos(cx, cy, cz + d); break;
    case 'left':          setViewPos(cx - d, cy, cz); break;
    case 'right':         setViewPos(cx + d, cy, cz); break;
    case 'top':           setViewPos(cx, cy + d, cz + 0.01); break;
  }}
}};

// ═══════════════════════════════════════════════════════════════════════
// Raycaster tooltip + animation loop
// ═══════════════════════════════════════════════════════════════════════
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
const tooltip = document.getElementById('tooltip');

renderer.domElement.addEventListener('mousemove', (e) => {{
  mouse.x = (e.clientX / innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;
}});

function animate() {{
  requestAnimationFrame(animate);
  controls.update();

  raycaster.setFromCamera(mouse, camera);
  let found = false;
  for (const mesh of blockMeshes) {{
    const hits = raycaster.intersectObject(mesh);
    if (hits.length > 0) {{
      const idx = hits[0].instanceId;
      const bl = mesh.userData.blocks[idx];
      if (bl) {{
        tooltip.textContent = bl.b + ' @ (' + bl.x + ', ' + bl.y + ', ' + bl.z + ')';
        found = true;
      }}
      break;
    }}
  }}
  if (!found) tooltip.textContent = 'Hover a block to identify';

  renderer.render(scene, camera);
}}
animate();

addEventListener('resize', () => {{
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
}});

{tabs_js}
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Preview saved to {output_path}")
    return output_path
