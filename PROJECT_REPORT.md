# Informe del Proyecto

## Descripción del proyecto

Este proyecto es un asistente de redacción en español diseñado para ofrecer autocompletado de frases y correcciones ligeras en tiempo real. La aplicación combina un backend en FastAPI con un frontend minimalista que simula la experiencia de escritura de un editor de texto. El objetivo principal es ayudar a redactar en español con sugerencias de continuación natural y un flujo de trabajo suave, sin forzar al usuario a escribir cada palabra.

La solución está pensada para redactores, estudiantes y profesionales que quieren avanzar en un texto con menos interrupciones. En lugar de funcionar como un corrector ortográfico rígido, el proyecto propone un asistente contextual que sugiere el siguiente fragmento de frase cuando el usuario está escribiendo, reduciendo la necesidad de buscar expresiones o pensar en la estructura completa de la oración.

El backend utiliza PyTorch para cargar un modelo recurrente de caracteres y un corpus de texto en español para generar sugerencias de frase. Este modelo no solo sugiere la palabra siguiente, sino fragmentos de frase coherentes basados en el contexto reciente del texto ya escrito. Para mantener la calidad, el sistema incluye un conjunto de reglas de validación y filtrado de frases que excluyen secuencias inválidas, repeticiones extrañas y combinaciones que no resultan naturales.

El frontend está construido con HTML, CSS y JavaScript liviano, y está diseñado como un editor suave y limpio. La interfaz presenta sugerencias inline mediante texto fantasma (`ghost text`), de modo que el usuario puede ver la continuación propuesta directamente en la misma línea donde escribe. Esto permite una experiencia similar a herramientas modernas de autocompletado, donde las recomendaciones se integran visualmente con el texto existente.

La interacción es simple: mientras se escribe, el backend genera sugerencias de frase y el frontend las muestra en tiempo real; el usuario puede aceptar la sugerencia activa pulsando `Tab`. También se diseñó un mecanismo de navegación con las teclas de dirección para seleccionar alternativas dentro de la lista de sugerencias disponibles. Todo esto se implementa sin saturar la UI, manteniendo un diseño minimalista que prioriza la escritura.

Además, el proyecto incorpora una arquitectura de despliegue basada en Docker. Se crearon Dockerfiles separados para backend y frontend, lo que facilita levantar la aplicación localmente o en servidores con contenedores. El despliegue puede hacerse con `docker compose`, que orquesta ambas piezas y garantiza reinicio automático (`restart: always`). De esta manera, el sistema no necesita configuración compleja y puede ejecutarse como un servicio confiable.

El resultado final es un asistente práctico y usable para apoyo de redacción en español: ofrece continuidad de frases, reduce el esfuerzo mental de estructurar oraciones y aporta una sensación de edición fluida sin complicaciones técnicas visibles para el usuario.

## Proceso de implementación y despliegue

### Estructura del proyecto
- `model/`: contiene scripts de entrenamiento, el modelo guardado y los datos del corpus.
- `back/`: contiene el backend FastAPI, el servidor y las definiciones de corrección/sugerencia.
- `fron/`: contiene el frontend HTML, CSS y JavaScript para la interfaz de usuario.

### Implementación
1. Se desarrolló un backend en `back/main.py` con FastAPI y CORS habilitado.
2. Se incluyó el modelo PyTorch en `model/saved_model.pt` y se prepararon utilidades de lectura de corpus con manejo de codificación y mojibake.
3. Se creó un frontend en `fron/index.html` con un editor simple y un overlay de sugerencias inline.
4. Se mejoró la experiencia de usuario para que las sugerencias aparezcan junto al texto y se acepten con `Tab`.
5. Se pulió el filtrado de frases para evitar resultados con tokens inválidos, pares de palabras extraños y sugerencias de baja calidad.

### Despliegue
1. Se añadieron Dockerfiles separados:
   - `back/Dockerfile` para la imagen del backend.
   - `fron/Dockerfile` para la imagen del frontend.
2. Se creó `publish_docker.sh` para construir imágenes locales y opcionalmente etiquetarlas y subirlas a Docker Hub.
3. El script ahora soporta:
   - construir solo localmente: `./publish_docker.sh`
   - construir y subir con usuario Docker Hub: `./publish_docker.sh TU_USUARIO`
   - construir y subir con usuario y nombre de repo: `./publish_docker.sh TU_USUARIO NOMBRE_REPO`
4. Se añadió un caché precomputado (`model/corpus_cache.pkl`) para evitar incluir el corpus completo dentro de la imagen Docker del backend.
5. Se inicializó un repositorio Git local y se creó `.gitignore` y `.dockerignore` para excluir dependencias y datos voluminosos.

## Funcionalidad

La aplicación ofrece las siguientes funciones:
- Autocompletado de frases en vivo mientras se escribe.
- Sugerencias inline colocadas directamente en el área de texto.
- Aplicación de la sugerencia activa con `Tab`.
- Corrección de palabras a partir del corpus y el modelo cargado.
- Interfaz minimalista y limpia, con foco en la escritura.

### Captura de pantalla de uso y funcionalidad

![Captura de uso y funcionalidad](screenshots/usage.png)

> Reemplaza esta imagen con una captura real del editor en funcionamiento. El archivo sugerido es `screenshots/usage.png`.

## Rutas de código y Docker

### Código local
- Ruta del proyecto: `/Users/david/ia/rnn`
- Backend: `/Users/david/ia/rnn/back`
- Frontend: `/Users/david/ia/rnn/fron`
- Modelo y datos: `/Users/david/ia/rnn/model`

### GitHub
- El repositorio local ahora está conectado a GitHub en:
  `https://github.com/echodavid/RNN_autocompletePrhase.git`
- La rama `main` fue empujada al remoto exitosamente.
- Si necesitas volver a configurar o usar SSH en el futuro:
  ```bash
  cd /Users/david/ia/rnn
  git remote add origin git@github.com:echodavid/RNN_autocompletePrhase.git
  git branch -M main
  git push -u origin main
  ```

### Imágenes Docker publicadas
- `echodavid/rnn-back:latest`
- `echodavid/rnn-front:latest`

### Instrucciones de ejecución local
1. Backend:
   ```bash
   docker run -p 8001:8001 rnn-back:latest
   ```
2. Frontend:
   ```bash
   docker run -p 5500:5500 rnn-front:latest
   ```

---

Este documento resume el estado actual del proyecto, su despliegue y los artefactos de Docker generados.