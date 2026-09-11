#--------Stage 1: Build the static React bundle --------------
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build 

#----------Stage 2: Serve it with Nginx---------------
FROM nginx: 1.27-alpine

# Remove the default nginx welcome page 
RUN rm /etc/nginx/conf.d/default.conf

RUN nginx.conf /etc/nginx/conf.d/default.conf
RUN --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

cmd ["nginx","-g","deamon --off;"]
