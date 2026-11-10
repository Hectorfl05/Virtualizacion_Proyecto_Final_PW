# Stage 1: solo copiamos los archivos estáticos
FROM nginx:1.27-alpine

# Usuario no-root 
RUN addgroup -g 10001 appgroup && \
    adduser -D -u 10001 -G appgroup appuser

COPY nginx.conf /etc/nginx/nginx.conf
COPY public/ /usr/share/nginx/html/

# Permisos
RUN chown -R appuser:appgroup /usr/share/nginx/html && \
    chown -R appuser:appgroup /var/cache/nginx && \
    chown -R appuser:appgroup /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown appuser:appgroup /var/run/nginx.pid

USER appuser

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
