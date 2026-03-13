use crate::models::Layer;

/// Classify a source file into an architectural layer.
/// Path segments are checked first; import signals override when present.
pub fn classify(path: &str, imports: &[String]) -> Layer {
    if is_config(path) {
        return Layer::Config;
    }

    let mut frontend_score: i32 = 0;
    let mut backend_score: i32 = 0;

    // Import signals are stronger — weight them higher
    for imp in imports {
        if is_frontend_import(imp) { frontend_score += 2; }
        if is_backend_import(imp)  { backend_score += 2; }
    }

    // Path segment signals
    for seg in path.to_lowercase().split('/') {
        if is_frontend_segment(seg) { frontend_score += 1; }
        if is_backend_segment(seg)  { backend_score += 1; }
    }

    match frontend_score.cmp(&backend_score) {
        std::cmp::Ordering::Greater => Layer::Frontend,
        std::cmp::Ordering::Less    => Layer::Backend,
        std::cmp::Ordering::Equal if frontend_score > 0 => Layer::Unknown, // ambiguous
        _ => {
            // No directional signal — check for shared indicators
            for seg in path.to_lowercase().split('/') {
                if is_shared_segment(seg) { return Layer::Shared; }
            }
            Layer::Unknown
        }
    }
}

fn is_config(path: &str) -> bool {
    let p = path.to_lowercase();
    p.ends_with(".config.ts") || p.ends_with(".config.js") ||
    p.ends_with(".config.mjs") || p.ends_with(".config.cjs") ||
    p.contains("webpack") || p.contains("rollup") ||
    p.contains("jest.config") || p.contains("vitest.config") ||
    p.contains("tsconfig") || p.contains("babel.config") ||
    p.contains("vite.config")
}

fn is_frontend_segment(seg: &str) -> bool {
    matches!(seg,
        "component" | "components" | "pages" | "page" | "views" | "view" |
        "ui" | "hooks" | "hook" | "layouts" | "layout" | "client" |
        "frontend" | "web" | "assets" | "static" | "public" |
        "widgets" | "widget" | "screens" | "screen"
    )
}

fn is_backend_segment(seg: &str) -> bool {
    matches!(seg,
        "server" | "api" | "route" | "routes" | "router" | "routers" |
        "controller" | "controllers" | "middleware" | "middlewares" |
        "service" | "services" | "db" | "database" | "model" | "models" |
        "backend" | "handler" | "handlers" | "repository" | "repositories" |
        "repo" | "storage" | "persistence" | "jobs" | "worker" | "workers" |
        "queue" | "queues" | "migrations" | "migration"
    )
}

fn is_shared_segment(seg: &str) -> bool {
    matches!(seg,
        "shared" | "common" | "utils" | "util" | "helpers" | "helper" |
        "types" | "type" | "lib" | "libs" | "constants" | "constant" |
        "core" | "domain" | "interfaces" | "dto" | "dtos" |
        "validators" | "validator" | "schemas" | "schema"
    )
}

fn is_frontend_import(imp: &str) -> bool {
    imp == "react" || imp == "react-dom" || imp == "react-router" ||
    imp == "react-router-dom" || imp.starts_with("react-") ||
    imp == "vue" || imp.starts_with("@vue/") ||
    imp == "svelte" || imp.starts_with("svelte/") ||
    imp.starts_with("@angular/") || imp.starts_with("@ng/") ||
    imp == "preact" || imp.starts_with("preact/") ||
    imp == "solid-js" || imp.starts_with("solid-js/") ||
    imp == "next" || imp.starts_with("next/") ||
    imp == "nuxt" || imp.starts_with("nuxt/") || imp.starts_with("@nuxt/") ||
    imp == "gatsby"
}

fn is_backend_import(imp: &str) -> bool {
    // JS/TS server frameworks
    imp == "express" || imp.starts_with("express-") ||
    imp == "fastify" || imp.starts_with("@fastify/") ||
    imp == "koa" || imp.starts_with("koa-") ||
    imp == "@hapi/hapi" || imp.starts_with("@hapi/") ||
    imp.starts_with("@nestjs/") ||
    // Databases / ORMs
    imp == "prisma" || imp.starts_with("@prisma/") ||
    imp == "mongoose" || imp == "pg" || imp == "pg-native" ||
    imp == "mysql" || imp == "mysql2" ||
    imp == "sqlite3" || imp == "better-sqlite3" ||
    imp == "redis" || imp.starts_with("ioredis") ||
    imp == "typeorm" || imp == "sequelize" || imp == "knex" ||
    imp == "drizzle-orm" || imp.starts_with("drizzle-") ||
    // Python server frameworks
    imp == "flask" || imp == "fastapi" || imp == "django" ||
    imp == "uvicorn" || imp == "starlette" || imp == "aiohttp" ||
    imp == "tornado" || imp == "sanic" || imp == "litestar" ||
    // Python databases
    imp == "sqlalchemy" || imp == "alembic" || imp == "pymongo" ||
    imp == "psycopg2" || imp == "asyncpg" || imp == "motor" ||
    imp == "databases" || imp == "tortoise" ||
    // Go server / database
    imp.contains("net/http") || imp.contains("database/sql") ||
    imp.contains("gin-gonic/gin") || imp.contains("gorilla/mux") ||
    imp.contains("labstack/echo") || imp.contains("go-chi/chi") ||
    imp.contains("gofiber/fiber") || imp.contains("gorm.io") ||
    imp.contains("go-redis/redis") || imp.contains("jackc/pgx")
}
