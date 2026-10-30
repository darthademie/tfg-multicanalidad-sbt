# Usamos la versión slim para que la imagen pese lo mínimo posible
FROM python:3.11-slim

# Evitar que Python genere archivos .pyc en el contenedor
ENV PYTHONDONTWRITEBYTECODE=1
# Forzar a que los logs (prints) salgan directos a la consola sin buffer (clave para verlos en ArgoCD/k0s)
ENV PYTHONUNBUFFERED=1

# Crear un usuario sin privilegios por seguridad (evitamos correr como root)
RUN useradd -m botuser

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar solo el archivo de dependencias primero
# (Si modificas el código pero no los requirements, Podman reutilizará esta capa cacheada en segundos)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código fuente del backend
COPY . .

# Dar permisos al usuario sin privilegios sobre la carpeta
RUN chown -R botuser:botuser /app

# Cambiar al usuario seguro
USER botuser

# Ejecutar el script principal
CMD ["python", "main.py"]