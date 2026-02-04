FROM nginx:1.29-alpine

# Copy nginx configuration
COPY conf.d/nginx.conf /etc/nginx/nginx.conf
COPY conf.d/default.conf /etc/nginx/conf.d/default.conf

# Copy static files
COPY static /usr/share/nginx/html
