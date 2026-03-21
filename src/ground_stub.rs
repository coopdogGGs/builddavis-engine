use crate::coordinate_system::cartesian::XZPoint;
#[derive(Clone)]
pub struct Ground {
    pub elevation_enabled: bool,
    ground_level: i32,
}
impl Ground {
    pub fn new_flat(ground_level: i32) -> Self {
        Self { elevation_enabled: false, ground_level }
    }
    #[inline(always)]
    pub fn level(&self, _coord: XZPoint) -> i32 {
        self.ground_level
    }
}
