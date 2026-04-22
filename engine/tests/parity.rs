use archlens_engine::analyze::{analyze_files, InputFile};
use std::fs;
use std::path::Path;

fn load_test_files() -> Vec<InputFile> {
    let test_dir = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("test-repos/sample-api");

    let mut files = Vec::new();
    for entry in fs::read_dir(&test_dir).unwrap() {
        let entry = entry.unwrap();
        let path = entry.path();
        if path.extension().map(|e| e == "py").unwrap_or(false) {
            let rel_path = path
                .file_name()
                .unwrap()
                .to_str()
                .unwrap()
                .to_string();
            let content = fs::read_to_string(&path).unwrap();
            files.push(InputFile {
                path: rel_path,
                content,
            });
        }
    }
    files.sort_by(|a, b| a.path.cmp(&b.path));
    files
}

#[test]
fn parity_nodes() {
    let files = load_test_files();
    let result = analyze_files(files);
    let golden: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(
            Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/sample-api-golden.json"),
        )
        .unwrap(),
    )
    .unwrap();

    let golden_nodes = golden["nodes"].as_array().unwrap();

    // Check node count
    assert_eq!(
        result.nodes.len(),
        golden_nodes.len(),
        "Node count mismatch: got {}, expected {}",
        result.nodes.len(),
        golden_nodes.len()
    );

    // Check each node
    let result_json: serde_json::Value = serde_json::to_value(&result).unwrap();
    let result_nodes = result_json["nodes"].as_array().unwrap();

    for (i, (got, expected)) in result_nodes.iter().zip(golden_nodes.iter()).enumerate() {
        assert_eq!(
            got["id"], expected["id"],
            "Node {} id mismatch",
            i
        );
        assert_eq!(
            got["label"], expected["label"],
            "Node {} label mismatch (id: {})",
            i, expected["id"]
        );
        assert_eq!(
            got["kind"], expected["kind"],
            "Node {} kind mismatch (id: {})",
            i, expected["id"]
        );
        assert_eq!(
            got["metrics"], expected["metrics"],
            "Node {} metrics mismatch (id: {})",
            i, expected["id"]
        );

        // Check optional fields
        if expected.get("isHot").is_some() {
            assert_eq!(
                got["isHot"], expected["isHot"],
                "Node {} isHot mismatch (id: {})",
                i, expected["id"]
            );
        } else {
            assert!(
                got.get("isHot").is_none() || got["isHot"].is_null(),
                "Node {} should not have isHot (id: {})",
                i, expected["id"]
            );
        }

        if expected.get("vulnerability").is_some() {
            assert_eq!(
                got["vulnerability"], expected["vulnerability"],
                "Node {} vulnerability mismatch (id: {})",
                i, expected["id"]
            );
        }
    }
}

#[test]
fn parity_layout() {
    let files = load_test_files();
    let result = analyze_files(files);
    let golden: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(
            Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/sample-api-golden.json"),
        )
        .unwrap(),
    )
    .unwrap();

    let golden_nodes = golden["nodes"].as_array().unwrap();
    let result_json: serde_json::Value = serde_json::to_value(&result).unwrap();
    let result_nodes = result_json["nodes"].as_array().unwrap();

    for (got, expected) in result_nodes.iter().zip(golden_nodes.iter()) {
        let id = expected["id"].as_str().unwrap();
        assert_eq!(
            got["x"], expected["x"],
            "Node {} x mismatch: got {}, expected {}",
            id, got["x"], expected["x"]
        );
        assert_eq!(
            got["y"], expected["y"],
            "Node {} y mismatch: got {}, expected {}",
            id, got["y"], expected["y"]
        );
        assert_eq!(
            got["width"], expected["width"],
            "Node {} width mismatch",
            id
        );
    }
}

#[test]
fn parity_edges() {
    let files = load_test_files();
    let result = analyze_files(files);
    let golden: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(
            Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/sample-api-golden.json"),
        )
        .unwrap(),
    )
    .unwrap();

    let golden_edges = golden["edges"].as_array().unwrap();
    let result_json: serde_json::Value = serde_json::to_value(&result).unwrap();
    let result_edges = result_json["edges"].as_array().unwrap();

    assert_eq!(
        result_edges.len(),
        golden_edges.len(),
        "Edge count mismatch: got {}, expected {}",
        result_edges.len(),
        golden_edges.len()
    );

    for (i, (got, expected)) in result_edges.iter().zip(golden_edges.iter()).enumerate() {
        assert_eq!(
            got["source"], expected["source"],
            "Edge {} source mismatch (expected id: {})",
            i, expected["id"]
        );
        assert_eq!(
            got["target"], expected["target"],
            "Edge {} target mismatch (expected id: {})",
            i, expected["id"]
        );
        assert_eq!(
            got["kind"], expected["kind"],
            "Edge {} kind mismatch (id: {})",
            i, expected["id"]
        );
    }
}

#[test]
fn parity_callers() {
    let files = load_test_files();
    let result = analyze_files(files);
    let golden: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(
            Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/sample-api-golden.json"),
        )
        .unwrap(),
    )
    .unwrap();

    let golden_callers = golden["callers"].as_object().unwrap();
    let result_json: serde_json::Value = serde_json::to_value(&result).unwrap();
    let result_callers = result_json["callers"].as_object().unwrap();

    assert_eq!(
        result_callers.len(),
        golden_callers.len(),
        "Callers map size mismatch"
    );

    for (key, expected_list) in golden_callers {
        let got_list = result_callers
            .get(key)
            .unwrap_or_else(|| panic!("Missing callers for {}", key));
        assert_eq!(
            got_list.as_array().unwrap().len(),
            expected_list.as_array().unwrap().len(),
            "Callers count mismatch for {}",
            key
        );
    }
}

#[test]
fn parity_stats() {
    let files = load_test_files();
    let result = analyze_files(files);
    let golden: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(
            Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/sample-api-golden.json"),
        )
        .unwrap(),
    )
    .unwrap();

    let gs = &golden["stats"];
    // Git info is injected separately, so only check counts
    assert_eq!(result.stats.functions, gs["functions"].as_i64().unwrap() as i32);
    assert_eq!(result.stats.classes, gs["classes"].as_i64().unwrap() as i32);
    assert_eq!(result.stats.modules, gs["modules"].as_i64().unwrap() as i32);
    assert_eq!(result.stats.vulns, gs["vulns"].as_i64().unwrap() as i32);
}

#[test]
fn parity_file_edges() {
    let files = load_test_files();
    let result = analyze_files(files);
    let golden: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(
            Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/sample-api-golden.json"),
        )
        .unwrap(),
    )
    .unwrap();

    let golden_fe = golden["fileEdges"].as_array().unwrap();

    // Compare as sets (order may differ)
    let mut golden_set: Vec<(String, String, i64)> = golden_fe
        .iter()
        .map(|e| {
            (
                e["source"].as_str().unwrap().to_string(),
                e["target"].as_str().unwrap().to_string(),
                e["callCount"].as_i64().unwrap(),
            )
        })
        .collect();
    golden_set.sort();

    let mut result_set: Vec<(String, String, i64)> = result
        .file_edges
        .iter()
        .map(|e| (e.source.clone(), e.target.clone(), e.call_count as i64))
        .collect();
    result_set.sort();

    assert_eq!(
        result_set.len(),
        golden_set.len(),
        "File edge count mismatch"
    );

    for (got, expected) in result_set.iter().zip(golden_set.iter()) {
        assert_eq!(got, expected, "File edge mismatch");
    }
}
