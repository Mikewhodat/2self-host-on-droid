FROM nvcr.io/nvidia/cuda:12.2.0-devel-ubuntu22.04

LABEL maintainer="webafy unified prod stack"

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk \
    maven \
    python3 python3-pip python3-venv \
    nginx \
    supervisor \
    mariadb-server \
    php8.1 php8.1-fpm php8.1-mysql php8.1-curl php8.1-gd php8.1-mbstring php8.1-xml php8.1-zip \
    unzip curl wget git nano htop \
    && rm -rf /var/lib/apt/lists/*

# Install WordPress
WORKDIR /var/www/html
RUN curl -O https://wordpress.org/latest.zip && \
    unzip latest.zip && \
    rm latest.zip && \
    chown -R www-data:www-data /var/www/html && \
    chmod -R 755 /var/www/html

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set up application directories
WORKDIR /app
COPY ./src /app/src
COPY ./java-backend /app/java-backend
COPY ./python-backend /app/python-backend
COPY ./nginx.conf /etc/nginx/nginx.conf
COPY ./supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy Flask proxy
COPY ./python-backend/proxy.py /app/ollama_proxy.py

# Copy DB init script
COPY init-wordpress-db.sh /usr/local/bin/init-wordpress-db.sh
RUN chmod +x /usr/local/bin/init-wordpress-db.sh

# Build Java backend
WORKDIR /app/java-backend
RUN mvn clean package -DskipTests

# Set up Python backend
WORKDIR /app/python-backend
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Install Flask and requests for the proxy
RUN pip3 install flask flask-cors requests

# Create necessary directories and set permissions
RUN mkdir -p /data/chroma /data/mysql /var/log/supervisor /var/run/mysqld /var/run/supervisor /run/php && \
    chmod -R 777 /data /var/www/html /var/run/supervisor /var/log/supervisor && \
    chown -R root:root /var/run/supervisor /var/log/supervisor && \
    chmod 755 /data/mysql && \
    chown -R mysql:mysql /data/mysql /var/run/mysqld

# Configure PHP-FPM
RUN sed -i 's/;daemonize = yes/daemonize = no/' /etc/php/8.1/fpm/php-fpm.conf && \
    sed -i 's/;error_log = log\/php8.1-fpm.log/error_log = \/var\/log\/php-fpm-error.log/' /etc/php/8.1/fpm/php-fpm.conf && \
    sed -i 's/listen = \/run\/php\/php8.1-fpm.sock/listen = 127.0.0.1:9000/' /etc/php/8.1/fpm/pool.d/www.conf

# Copy static files to nginx html directory
RUN cp -r /app/src/* /usr/share/nginx/html/ 2>/dev/null || true

# Initialize MySQL data directory
RUN mysql_install_db --user=mysql --datadir=/data/mysql

# Start MySQL, initialize WordPress database, then stop
RUN mysqld_safe --user=mysql --datadir=/data/mysql --socket=/var/run/mysqld/mysqld.sock & \
    sleep 20 && \
    /usr/local/bin/init-wordpress-db.sh && \
    mysqladmin -u root --socket=/var/run/mysqld/mysqld.sock shutdown

# Pre-pull Ollama models
RUN nohup ollama serve > /tmp/ollama.log 2>&1 & \
    sleep 30 && \
    ollama pull nomic-embed-text:latest && \
    ollama pull konsumer/weather:latest && \
    ollama pull deepseek-r1:14b && \
    pkill -f "ollama serve" && \
    sleep 5

# Validate configuration
RUN nginx -t && \
    which uvicorn && \
    which ollama && \
    which supervisord && \
    python3 -c "import chromadb; print('ChromaDB OK')" && \
    python3 -c "import flask; print('Flask OK')" && \
    python3 -c "import flask_cors; print('Flask-CORS OK')" && \
    python3 -c "import requests; print('Requests OK')"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost/health || curl -f http://localhost:5000/health || exit 1

EXPOSE 80 443 8000 8080 8123 11434 5000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]