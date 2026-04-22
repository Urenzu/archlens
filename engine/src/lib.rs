pub mod analyze;
pub mod classifier;
pub mod graph;
pub mod hotpath;
pub mod layout;
pub mod metrics;
pub mod models;
pub mod parser;
pub mod vulnerability;

pub fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_exists() {
        assert!(!version().is_empty());
    }
}
