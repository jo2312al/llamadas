.PHONY: instalar formato validar probar ejecutar migrar desplegar estado respaldar instalar-asterisk configurar-asterisk
instalar:
	python -m pip install -r requirements-dev.txt
formato:
	black .
	ruff check --fix .
validar:
	ruff check .
	black --check .
	python -m compileall -q aplicacion pruebas
probar:
	python -m pytest
ejecutar:
	python -m aplicacion.principal conversar
migrar:
	python -m aplicacion.principal migrar
desplegar:
	./scripts/desplegar.sh
estado:
	./scripts/verificar_estado.sh
respaldar:
	./scripts/respaldar_base_datos.sh
instalar-asterisk:
	./scripts/instalar_asterisk.sh
configurar-asterisk:
	./scripts/configurar_asterisk.sh
