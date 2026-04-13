FROM node:20-alpine AS build

WORKDIR /web

ARG VITE_TERM_START_DATES=""
ARG VITE_DEFAULT_TERM_START_DATE=""
ENV VITE_TERM_START_DATES=$VITE_TERM_START_DATES
ENV VITE_DEFAULT_TERM_START_DATE=$VITE_DEFAULT_TERM_START_DATE

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html

EXPOSE 80
