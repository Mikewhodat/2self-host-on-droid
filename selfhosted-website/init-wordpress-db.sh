#!/bin/bash
set -e

# === Default fallback values ===
DEFAULT_DB_NAME="wordpress"
DEFAULT_DB_USER="wp_admin"
DEFAULT_DB_PASS="R25thnov!Gtp!!"

# === Use environment overrides if available ===
DB_NAME="${WORDPRESS_DB_NAME:-$DEFAULT_DB_NAME}"
DB_USER="${WORDPRESS_DB_USER:-$DEFAULT_DB_USER}"
DB_PASS="${WORDPRESS_DB_PASS:-$DEFAULT_DB_PASS}"

MYSQL_SOCKET="/var/run/mysqld/mysqld.sock"

echo ""
echo "== 🛠 WordPress DB Init Script =="
echo "Database Name    : $DB_NAME"
echo "User             : $DB_USER"
echo "Password         : $DB_PASS"
echo "Using socket     : $MYSQL_SOCKET"
echo "Source           :"
echo "    WORDPRESS_DB_USER=${WORDPRESS_DB_USER:-<not set, using default>}"
echo "    WORDPRESS_DB_PASS=${WORDPRESS_DB_PASS:+<set>}${WORDPRESS_DB_PASS:+ (not shown)}"
echo ""

# Wait for MariaDB to be available
echo "⏳ Waiting for MariaDB to be ready..."
for i in {30..0}; do
    if mysqladmin ping -u root --socket="$MYSQL_SOCKET" --silent; then
        echo "✅ MariaDB is up."
        break
    fi
    sleep 1
done

echo "🚧 Creating database and user if not already present..."
mysql -u root --socket="$MYSQL_SOCKET" <<EOF
CREATE DATABASE IF NOT EXISTS \`$DB_NAME\`;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
EOF

echo "✅ Done. '$DB_NAME' is ready with user '$DB_USER'."
