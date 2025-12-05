FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Instalar dependencias del sistema (VITAL)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Instalar librerías esenciales (para evitar el ModuleNotFoundError)
RUN pip install --no-cache-dir Flask pandas numpy matplotlib seaborn scikit-learn scipy Pillow google-generativeai tabulate contourpy requests tenacity

# Copiar el código
COPY . /app

# Configurar el puerto y el comando de inicio (ASUMIENDO app.py está en la raíz del contenedor)
ENV PORT 8080
CMD ["python", "app.py"]
