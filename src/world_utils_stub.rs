use std::path::{Path, PathBuf};
pub fn get_bedrock_output_directory() -> PathBuf {
    dirs::desktop_dir().or_else(dirs::home_dir).unwrap_or_else(|| PathBuf::from("."))
}
pub fn sanitize_for_filename(name: &str) -> String { name.to_string() }
pub fn build_bedrock_output(bbox: &crate::coordinate_system::geographic::LLBBox, output_dir: PathBuf) -> (PathBuf, String) {
    let name = "Build Davis".to_string();
    (output_dir.join("Build Davis.mcworld"), name)
}
pub fn create_new_world(base_path: &Path) -> Result<String, String> {
    Ok(base_path.to_string_lossy().to_string())
}
pub fn set_spawn_in_level_dat(_world_path: &Path, _spawn_x: i32, _spawn_z: i32) -> Result<(), String> {
    Ok(())
}
