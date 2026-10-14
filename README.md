# Astro

Hice una página para ver cosas del espacio. Tiene planetas, estrellas y más.

## Qué tiene

- Catálogo para buscar planetas y estrellas
- Comparador para ver dos planetas lado a lado
- Simulador para calcular viajes en el espacio
- Cuestionario para responder preguntas
- Favoritos para guardar lo que me gusta

## Cómo lo hice

Usé gRPC con 3 servicios:

- Uno para el catálogo (puerto 50051)
- Otro para los cálculos de viajes (puerto 50052)
- Otro para las preguntas (puerto 50053)

Y una página web que se conecta a esos servicios.

## Cómo correrlo

Primero instalar lo necesario:

```bat
pip install -r requirements.txt
python generate_proto.py
```

Después abrir 4 terminales:

```bat
python server\catalog_server.py
python server\simulation_server.py
python server\quiz_server.py
python gateway\app.py
```

Al final abrir en el navegador:

```
http://localhost:8080
```
