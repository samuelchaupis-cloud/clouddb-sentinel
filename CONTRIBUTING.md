# Guía de Contribución — CloudDB Sentinel

¡Gracias por tu interés en contribuir a **CloudDB Sentinel**!

Este proyecto sigue estándares de calidad de software y prácticas DevOps para infraestructura crítica.

---

## 🛠️ Flujo de Trabajo para Contribuir

1. **Haz un Fork** del repositorio.
2. **Crea una rama** para tu funcionalidad o corrección:
   ```bash
   git checkout -b feature/nueva-funcionalidad
   # o
   git checkout -b fix/correccion-bug
   ```
3. **Instala las dependencias de desarrollo**:
   ```bash
   pip install -r requirements.txt
   pip install flake8 black pytest pytest-cov
   ```
4. **Realiza tus cambios** siguiendo las directrices de estilo PEP 8.
5. **Ejecuta las pruebas unitarias y de linting**:
   ```bash
   flake8 src tests --max-line-length=120
   pytest tests/ -v
   ```
6. **Haz commit** con mensajes claros y descriptivos siguiendo Conventional Commits:
   - `feat: agregar soporte para monitor de SQL Server`
   - `fix: corregir cálculo de regresión en bases de datos con pocos snapshots`
   - `docs: actualizar guía de entrevista y procedimientos SOP`
7. **Envía un Pull Request** hacia la rama `main`.

---

## 📋 Estándares de Código

- **Tipado estricto:** Usa `type hints` en todas las funciones y métodos nuevos.
- **Docstrings:** Documenta módulos, clases y funciones en español con formato Google/NumPy docstrings.
- **Manejo de Excepciones:** No uses `except Exception: pass`. Siempre captura excepciones específicas y registra los errores con el módulo `logging`.
