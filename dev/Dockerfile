FROM nginx:1.29-alpine

COPY dev/conf.d/nginx.conf /etc/nginx/nginx.conf
COPY dev/conf.d/default.conf /etc/nginx/conf.d/default.conf
COPY static /usr/share/nginx/html
