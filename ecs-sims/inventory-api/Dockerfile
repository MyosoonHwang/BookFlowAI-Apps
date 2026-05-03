FROM public.ecr.aws/nginx/nginx:1.27-alpine
# Build context = ecs-sims/ root (see buildspec.yml).
COPY inventory-api/default.conf /etc/nginx/conf.d/default.conf
COPY inventory-api/index.html /usr/share/nginx/html/index.html
EXPOSE 8080
