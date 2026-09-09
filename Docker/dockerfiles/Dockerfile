# build stage: 
FROM alpine:3.24.1 AS builder

WORKDIR /usr/src/app

RUN apk add --no-cache  bash
RUN rm -rf /var/cache/apk/* /tmp/* /var/tmp/*

COPY index.html styles.css ./

#Final stage
FROM nginx:alpine

LABEL maintainer="devops@example.com"
LABEL org.opencontainers.image.source="https://github.com/Rudrseh/Devops_journey"
LABEL org.opencontainers.image.description="Static website served by Nginx using a multi-stage Docker build."

ENV APP_NAME="Nginx Static Site"
ENV APP_ENV="development"
ENV NGINX_PORT=80

RUN addgroup -S webuser && adduser -S webuser -G webuser


COPY --from=builder /usr/src/app /usr/share/nginx/html
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]