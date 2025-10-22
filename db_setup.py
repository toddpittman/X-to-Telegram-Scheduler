import psycopg2
import os

def setup_database():
    """Create the scheduled_posts table"""
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id SERIAL PRIMARY KEY,
            chat_id VARCHAR(255) NOT NULL,
            content_text TEXT NOT NULL,
            media_files TEXT,
            channel_name VARCHAR(255),
            schedule_time TIMESTAMP NOT NULL,
            status VARCHAR(50) DEFAULT 'scheduled',
            user_name VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW(),
            posted_at TIMESTAMP,
            error TEXT
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("Database setup complete!")

if __name__ == "__main__":
    setup_database()