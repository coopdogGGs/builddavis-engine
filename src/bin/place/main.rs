//! BuildDavis Pipeline — Stage 6: Block Placement Engine
mod blocks_reader;

use arnis::block_definitions::*;
use arnis::coordinate_system::cartesian::XZBBox;
use arnis::coordinate_system::geographic::LLBBox;
use arnis::world_editor::{WorldEditor, WorldFormat};
use blocks_reader::parse_block_id;

use clap::Parser;
use flate2::write::GzEncoder;
use flate2::Compression;
use std::collections::HashMap;
use std::io::Write;
use std::path::PathBuf;
use std::time::Instant;

const DAVIS_MIN_LAT: f64 =  38.510;
const DAVIS_MIN_LNG: f64 = -121.780;
const DAVIS_MAX_LAT: f64 =  38.590;
const DAVIS_MAX_LNG: f64 = -121.690;

// Spawn Y: set high so Minecraft scans down to find our surface at Y=47
const SPAWN_Y: i32 = 320;

#[derive(Parser, Debug)]
#[command(about = "BuildDavis block placement engine")]
struct Args {
    #[arg(long)] blocks: PathBuf,
    #[arg(long)] output: PathBuf,
    #[arg(long, default_value = "Build Davis")] world_name: String,
    #[arg(long)] bedrock: bool,
    #[arg(long, allow_hyphen_values = true)] bbox: Option<String>,
    /// Spawn X coordinate in world space (before offset)
    #[arg(long, default_value_t = 0)] spawn_x: i32,
    /// Spawn Z coordinate in world space (before offset)
    #[arg(long, default_value_t = 0)] spawn_z: i32,
}

fn main() {
    let args = Args::parse();

    println!("============================================================");
    println!("  BuildDavis - Stage 6: Place");
    println!("============================================================");

    let total_start = Instant::now();

    println!("[1/6] Loading blocks.json...");
    let blocks_json = std::fs::read_to_string(&args.blocks)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", args.blocks.display()));
    let raw_blocks: Vec<serde_json::Value> = serde_json::from_str(&blocks_json)
        .unwrap_or_else(|e| panic!("Failed to parse blocks.json: {e}"));
    println!("  Loaded {} block entries", raw_blocks.len());

    println!("[2/6] Computing world bounds...");
    let mut min_x = i32::MAX; let mut max_x = i32::MIN;
    let mut min_z = i32::MAX; let mut max_z = i32::MIN;
    for b in &raw_blocks {
        let x = b["x"].as_i64().unwrap_or(0) as i32;
        let z = b["z"].as_i64().unwrap_or(0) as i32;
        if x < min_x { min_x = x; } if x > max_x { max_x = x; }
        if z < min_z { min_z = z; } if z > max_z { max_z = z; }
    }
    min_x -= 16; min_z -= 16;
    max_x += 16; max_z += 16;
    let x_offset = -min_x + 16;
    let z_offset = -min_z + 16;
    println!("  X [{min_x}, {max_x}]  Z [{min_z}, {max_z}]");
    println!("  Offset: X+{x_offset} Z+{z_offset}");

    let width = (max_x - min_x) as f64;
    let depth = (max_z - min_z) as f64;
    let xzbbox = XZBBox::rect_from_xz_lengths(width, depth)
        .unwrap_or_else(|e| panic!("Invalid XZBBox: {e}"));

    let llbbox = match args.bbox.as_deref() {
        Some(s) => parse_llbbox(s),
        None => LLBBox::new(DAVIS_MIN_LAT, DAVIS_MIN_LNG, DAVIS_MAX_LAT, DAVIS_MAX_LNG)
            .unwrap_or_else(|e| panic!("Invalid Davis LLBBox: {e}")),
    };

    std::fs::create_dir_all(&args.output)
        .unwrap_or_else(|e| panic!("Cannot create output dir: {e}"));

    // Spawn point in world coordinates (offset-adjusted)
    let spawn_x_world = args.spawn_x + x_offset;
    let spawn_z_world = args.spawn_z + z_offset;

    println!("[3/6] Placing {} blocks...", raw_blocks.len());
    let format = if args.bedrock { WorldFormat::BedrockMcWorld } else { WorldFormat::JavaAnvil };
    let mut editor = WorldEditor::new_with_format_and_name(
        args.output.clone(), &xzbbox, llbbox, format,
        Some(args.world_name.clone()), Some((spawn_x_world, spawn_z_world)),
    );

    let mut placed = 0u64; let mut skipped = 0u64; let mut unknown = 0u64;
    let report_every = (raw_blocks.len() / 20).max(10_000);

    for (i, b) in raw_blocks.iter().enumerate() {
        let x = b["x"].as_i64().unwrap_or(0) as i32 + x_offset;
        let y = b["y"].as_i64().unwrap_or(47) as i32;
        let z = b["z"].as_i64().unwrap_or(0) as i32 + z_offset;
        let block_id = b["block"].as_str().unwrap_or("minecraft:air");

        match parse_block_id(block_id) {
            Some(block) if block == AIR => { skipped += 1; }
            Some(block) => { editor.set_block_absolute(block, x, y, z, None, None); placed += 1; }
            None => { editor.set_block_absolute(STONE, x, y, z, None, None); unknown += 1; }
        }

        if i > 0 && i % report_every == 0 {
            let pct = i as f64 / raw_blocks.len() as f64 * 100.0;
            println!("  {pct:.0}% ({placed} placed, {skipped} air, {unknown} unknown)");
        }
    }
    println!("  Done: {placed} placed, {skipped} air, {unknown} unknown->stone");

    println!("[4/6] Saving world...");
    let save_start = Instant::now();
    editor.save().unwrap_or_else(|e| panic!("Save failed: {e}"));
    println!("  Saved in {:.1}s", save_start.elapsed().as_secs_f64());

    // Write level.dat — void world, creative mode, cheats on
    println!("[5/6] Writing level.dat...");
    match write_level_dat(&args.output, &args.world_name, spawn_x_world, SPAWN_Y, spawn_z_world) {
        Ok(_)  => println!("  level.dat written (void world, creative, cheats on)"),
        Err(e) => eprintln!("  Warning: level.dat failed: {e}"),
    }

    println!("[6/6] Writing manifest...");
    let manifest = serde_json::json!({
        "stage": "place",
        "world_name": args.world_name,
        "format": if args.bedrock { "bedrock" } else { "java" },
        "output": args.output.to_string_lossy(),
        "blocks_placed": placed,
        "blocks_skipped": skipped,
        "blocks_unknown": unknown,
        "spawn": {"x": spawn_x_world, "y": SPAWN_Y, "z": spawn_z_world},
        "elapsed_seconds": total_start.elapsed().as_secs_f64(),
    });
    let _ = std::fs::write(
        args.output.join("place_manifest.json"),
        serde_json::to_string_pretty(&manifest).unwrap(),
    );

    println!();
    println!("============================================================");
    println!("  Stage 6 complete in {:.1}s", total_start.elapsed().as_secs_f64());
    println!("  Output:  {}", args.output.display());
    println!("  Spawn:   X={spawn_x_world} Y={SPAWN_Y} Z={spawn_z_world}");
    println!("  Blocks:  {placed} placed");
    println!("============================================================");
}

/// Write a minimal Java Edition level.dat.
///
/// Key settings:
///   generator=2  flat/void  — Minecraft generates NO natural terrain
///   GameType=1   creative
///   allowCommands=1  cheats on
///   LevelName    as passed
///   SpawnX/Y/Z   our actual spawn coordinates
fn write_level_dat(
    world_dir: &PathBuf,
    level_name: &str,
    spawn_x: i32,
    spawn_y: i32,
    spawn_z: i32,
) -> Result<(), Box<dyn std::error::Error>> {
    use fastnbt::Value;

    let now_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64;

    // Build the Data compound
    let mut data: HashMap<String, Value> = HashMap::new();
    data.insert("LevelName".into(),      Value::String(level_name.to_string()));
    data.insert("GameType".into(),       Value::Int(1));       // 0=survival 1=creative
    data.insert("Difficulty".into(),     Value::Int(0));       // peaceful
    data.insert("allowCommands".into(),  Value::Byte(1));      // cheats on
    data.insert("hardcore".into(),       Value::Byte(0));
    data.insert("initialized".into(),    Value::Byte(1));
    data.insert("LastPlayed".into(),     Value::Long(now_ms));
    data.insert("RandomSeed".into(),     Value::Long(0));
    data.insert("Time".into(),           Value::Long(6000));   // midday
    data.insert("DayTime".into(),        Value::Long(6000));
    data.insert("version".into(),        Value::Int(19133));   // Java 1.21 NBT version
    data.insert("DataVersion".into(),    Value::Int(3953));    // 1.21.1
    // Game rules
    data.insert("spawnMobs".into(),          Value::Byte(0));
    data.insert("doMobSpawning".into(),      Value::Byte(0));
    data.insert("keepInventory".into(),      Value::Byte(1));
    data.insert("doDaylightCycle".into(),    Value::Byte(1));
    data.insert("SpawnX".into(),             Value::Int(spawn_x));
    data.insert("SpawnY".into(),         Value::Int(spawn_y));
    data.insert("SpawnZ".into(),         Value::Int(spawn_z));

    // Void world generator settings
    // generator-name "flat" with void preset tells Minecraft: generate nothing
    let mut gen_options: HashMap<String, Value> = HashMap::new();
    gen_options.insert("biome".into(),   Value::String("minecraft:the_void".into()));
    gen_options.insert("features".into(), Value::Byte(0));
    gen_options.insert("lakes".into(),    Value::Byte(0));
    gen_options.insert("structures".into(), Value::Compound({
        let mut s = HashMap::new();
        s.insert("structures".into(), Value::Compound(HashMap::new()));
        s
    }));
    gen_options.insert("layers".into(),  Value::List(vec![])); // zero layers = void

    let mut gen_settings: HashMap<String, Value> = HashMap::new();
    gen_settings.insert("type".into(),
        Value::String("minecraft:flat".into()));
    gen_settings.insert("settings".into(),
        Value::Compound(gen_options));

    let mut world_gen: HashMap<String, Value> = HashMap::new();
    world_gen.insert("type".into(),
        Value::String("minecraft:overworld".into()));
    world_gen.insert("generator".into(),
        Value::Compound(gen_settings));

    let mut dimensions: HashMap<String, Value> = HashMap::new();
    dimensions.insert("minecraft:overworld".into(),
        Value::Compound(world_gen));

    let mut world_gen_settings: HashMap<String, Value> = HashMap::new();
    world_gen_settings.insert("bonus_chest".into(), Value::Byte(0));
    world_gen_settings.insert("generate_features".into(), Value::Byte(0));
    world_gen_settings.insert("seed".into(), Value::Long(0));
    world_gen_settings.insert("dimensions".into(),
        Value::Compound(dimensions));

    data.insert("WorldGenSettings".into(),
        Value::Compound(world_gen_settings));

    // Version info Minecraft needs to recognize the world
    let mut version: HashMap<String, Value> = HashMap::new();
    version.insert("Id".into(),       Value::Int(3953));
    version.insert("Name".into(),     Value::String("1.21.1".into()));
    version.insert("Series".into(),   Value::String("main".into()));
    version.insert("Snapshot".into(), Value::Byte(0));
    data.insert("Version".into(), Value::Compound(version));

    // Root NBT compound
    let mut root: HashMap<String, Value> = HashMap::new();
    root.insert("Data".into(), Value::Compound(data));

    // Serialize to NBT bytes
    let nbt_bytes = fastnbt::to_bytes(&Value::Compound(root))?;

    // Compress with gzip
    let mut encoder = GzEncoder::new(Vec::new(), Compression::default());
    encoder.write_all(&nbt_bytes)?;
    let compressed = encoder.finish()?;

    // Write to world directory
    let level_dat_path = world_dir.join("level.dat");
    std::fs::write(&level_dat_path, compressed)?;

    Ok(())
}

fn parse_llbbox(s: &str) -> LLBBox {
    let p: Vec<f64> = s.split(',')
        .map(|v| v.trim().parse().expect("bad coord"))
        .collect();
    assert_eq!(p.len(), 4);
    LLBBox::new(p[0], p[1], p[2], p[3])
        .unwrap_or_else(|e| panic!("Invalid bbox: {e}"))
}
