python generate_proto.py
start "CatalogService" python server\catalog_server.py
start "SimulationService" python server\simulation_server.py
start "QuizService" python server\quiz_server.py
start "Gateway" python gateway\app.py
echo AstroLink iniciado: abre http://localhost:8080
