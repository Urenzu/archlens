fn main() {
    let path = std::env::args().nth(1).unwrap_or_else(|| "/tmp/platform_files.json".to_string());
    let files_json = std::fs::read_to_string(&path).unwrap();
    let files: Vec<archlens_engine::analyze::InputFile> = serde_json::from_str(&files_json).unwrap();
    let result = archlens_engine::analyze::analyze_files(files);
    let parsed = serde_json::to_value(&result).unwrap();
    println!("nodes: {}", parsed["nodes"].as_array().unwrap().len());
    println!("edges: {}", parsed["edges"].as_array().unwrap().len());
    println!("modules: {}", parsed["modules"].as_array().unwrap().len());
    println!("stats: {}", parsed["stats"]);
    println!("\nFunctions:");
    for node in parsed["nodes"].as_array().unwrap() {
        if node["kind"] == "fn" {
            println!("  {} (complexity={})", node["label"], node["metrics"]["cyclomatic"]);
        }
    }
}
