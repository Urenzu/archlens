fn main() {
    let files_json = std::fs::read_to_string("/tmp/platform_files.json").unwrap();
    eprintln!("Input length: {} bytes", files_json.len());
    let result = archlens_engine::analyze(&files_json);
    let parsed: serde_json::Value = serde_json::from_str(&result).unwrap();
    println!("nodes: {}", parsed["nodes"].as_array().unwrap().len());
    println!("edges: {}", parsed["edges"].as_array().unwrap().len());
    println!("modules: {}", parsed["modules"].as_array().unwrap().len());
    let stats = &parsed["stats"];
    println!("stats: {}", stats);
}
