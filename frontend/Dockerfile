FROM nginx:1.29-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY static/ /usr/share/nginx/html/

CMD ["nginx", "-g", "daemon off;"]
