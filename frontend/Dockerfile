FROM nginx:alpine:1.29

COPY nginx.conf /etc/nginx/nginx.d/
COPY static/ /usr/share/nginx/html/

CMD ["nginx", "-g", "daemon off;"]
