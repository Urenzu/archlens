/// ArchLens high-performance analysis engine.
/// Will handle hot-path graph traversal, complexity scoring, and metrics aggregation.

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
