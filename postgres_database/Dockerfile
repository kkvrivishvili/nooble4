# Usar la imagen oficial de Postgres como base
FROM postgres:15-alpine

# La imagen oficial de Postgres ejecutará automáticamente cualquier script .sh, .sql, .sql.gz
# que se encuentre en el directorio /docker-entrypoint-initdb.d al iniciar el contenedor.
# Esto es ideal para crear bases de datos, roles o esquemas iniciales.
COPY init.sql /docker-entrypoint-initdb.d/
