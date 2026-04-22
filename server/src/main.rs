use std::path::{Path, PathBuf};
use std::process::Command;

use axum::{
    extract::Query,
    http::StatusCode,
    response::Json,
    routing::get,
    Router,
};
use serde::{Deserialize, Serialize};
use tower_http::cors::CorsLayer;
use tower_http::services::ServeDir;

use archlens_engine::analyze::InputFile;

#[derive(Deserialize)]
struct AnalyzeQuery {
    path: String,
}

#[derive(Serialize)]
struct HealthResponse {
    status: String,
}

/// Skip directories that should not be analyzed.
fn should_skip(component: &str) -> bool {
    component.starts_with('.')
        || component == "__pycache__"
        || component == "venv"
        || component == ".venv"
        || component == "node_modules"
}

/// Recursively collect files from a directory.
fn collect_files(dir: &Path, root: &Path, files: &mut Vec<InputFile>) -> std::io::Result<()> {
    let mut entries: Vec<_> = std::fs::read_dir(dir)?
        .filter_map(|e| e.ok())
        .collect();
    entries.sort_by_key(|e| e.file_name());

    for entry in entries {
        let path = entry.path();
        let file_name = entry.file_name();
        let name = file_name.to_str().unwrap_or("");

        if should_skip(name) {
            continue;
        }

        if path.is_dir() {
            collect_files(&path, root, files)?;
        } else if path.is_file() {
            if let Ok(rel) = path.strip_prefix(root) {
                let rel_str = rel.to_str().unwrap_or("").replace('\\', "/");
                if let Ok(content) = std::fs::read_to_string(&path) {
                    files.push(InputFile {
                        path: rel_str,
                        content,
                    });
                }
            }
        }
    }

    Ok(())
}

/// Extract git metadata from a repository.
fn get_git_info(repo_path: &Path) -> serde_json::Value {
    let run = |args: &[&str]| -> Option<String> {
        Command::new("git")
            .args(args)
            .current_dir(repo_path)
            .output()
            .ok()
            .filter(|o| o.status.success())
            .and_then(|o| String::from_utf8(o.stdout).ok())
            .map(|s| s.trim().to_string())
    };

    let branch = run(&["rev-parse", "--abbrev-ref", "HEAD"]).unwrap_or_else(|| "unknown".into());
    let commit = run(&["rev-parse", "--short", "HEAD"]).unwrap_or_else(|| "0000000".into());

    let mut name = repo_path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown")
        .to_string();

    if let Some(origin) = run(&["remote", "get-url", "origin"]) {
        let origin = origin.trim_end_matches(".git").trim_end_matches('/');
        // Handle both HTTPS (github.com/org/repo) and SSH (git@github.com:org/repo)
        let normalized = origin.replace(':', "/");
        let parts: Vec<&str> = normalized.split('/').collect();
        if parts.len() >= 2 {
            name = format!("{}/{}", parts[parts.len() - 2], parts[parts.len() - 1]);
        }
    }

    serde_json::json!({ "name": name, "branch": branch, "commit": commit })
}

async fn api_analyze(
    Query(params): Query<AnalyzeQuery>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let mut repo_path = PathBuf::from(&params.path);

    // Resolve relative paths
    if repo_path.is_relative() {
        if let Ok(cwd) = std::env::current_dir() {
            let candidate = cwd.join(&repo_path);
            if candidate.is_dir() {
                repo_path = candidate;
            } else if let Some(parent) = cwd.parent() {
                let candidate = parent.join(&repo_path);
                if candidate.is_dir() {
                    repo_path = candidate;
                }
            }
        }
    }

    if !repo_path.is_dir() {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("Not a directory: {}", params.path),
        ));
    }

    let repo_path = repo_path
        .canonicalize()
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;

    // Collect files
    let mut files = Vec::new();
    collect_files(&repo_path, &repo_path, &mut files)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    // Run analysis
    let result = archlens_engine::analyze::analyze_files(files);
    let mut json: serde_json::Value = serde_json::to_value(&result)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    // Inject git metadata into stats
    let git = get_git_info(&repo_path);
    if let Some(stats) = json.get_mut("stats").and_then(|s| s.as_object_mut()) {
        for (k, v) in git.as_object().unwrap() {
            stats.insert(k.clone(), v.clone());
        }
    }

    Ok(Json(json))
}

async fn api_health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".into(),
    })
}

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8000);

    let cors = CorsLayer::permissive();

    let frontend_dir = if PathBuf::from("frontend/dist").is_dir() {
        PathBuf::from("frontend/dist")
    } else {
        PathBuf::from("../frontend/dist")
    };

    let app = Router::new()
        .route("/api/analyze", get(api_analyze))
        .route("/api/health", get(api_health))
        .fallback_service(ServeDir::new(frontend_dir).append_index_html_on_directories(true))
        .layer(cors);

    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", port))
        .await
        .expect("failed to bind");

    println!("ArchLens server listening on http://0.0.0.0:{}", port);
    axum::serve(listener, app).await.expect("server error");
}
