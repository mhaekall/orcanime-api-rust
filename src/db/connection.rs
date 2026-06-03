use sqlx::{postgres::PgPoolOptions, PgPool};
use std::env;

pub async fn init_db() -> Result<PgPool, sqlx::Error> {
    let database_url = env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/postgres".to_string());
    
    // We use a connection pool to connect to Supabase
    // Using a connection pool ensures we don't open too many connections.
    let pool = PgPoolOptions::new()
        .max_connections(50) // Adjust based on HF space memory limits and Supabase tier
        .connect(&database_url)
        .await?;

    tracing::info!("✅ Successfully connected to Supabase Postgres.");

    Ok(pool)
}
