#!/bin/bash

# Initialize SQLite database
DB_FILE="proxy.db"

if [ -f "$DB_FILE" ]; then
    echo "Database already exists: $DB_FILE"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm "$DB_FILE"
        echo "Deleted existing database"
    else
        echo "Keeping existing database"
        exit 0
    fi
fi

echo "Creating SQLite database..."
sqlite3 "$DB_FILE" < init-sqlite.sql

if [ $? -eq 0 ]; then
    echo "✅ Database initialized successfully!"
    echo ""
    echo "Demo service keys created:"
    echo "  - sk-test-demo-key-12345678 (free, 1000/day)"
    echo "  - sk-test-basic-key-11111111 (basic, 5000/day)"
    echo "  - sk-test-premium-key-22222222 (premium, 20000/day)"
    echo "  - sk-test-enterprise-key-33333333 (enterprise, 100000/day)"
    echo ""
    echo "Admin credentials:"
    echo "  - Username: admin"
    echo "  - Password: admin123"
else
    echo "❌ Failed to initialize database"
    exit 1
fi
