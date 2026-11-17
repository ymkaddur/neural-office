# Documentación

## Usar la versión actual

- [Compilar y abrir el escritorio](../desktop/README.md).
- [Revisión HTML y referencia sin modelo](HTML_REVIEW.md).
- [Qué aportó cada perfil en V5.7](V5_7_REVIEW.md).
- [Hoja de ruta hacia V6](../ROADMAP.md).
- [Datos, límites y seguridad](../SECURITY.md), [licencias](../LICENSING.md) y [apoyo voluntario](SUPPORT.md).

## Estado existente y herramientas Python

El escritorio utiliza el mismo estado del piloto. No borres el ledger para actualizar ni para recuperar cuota. Si conservas un estado V5.2 sin proteger, cierra sus controladores y consulta primero [protección, respaldo, restauración y conciliación](V5_2_1_OPERATIONS.md).

`run.bat` abre la interfaz Python heredada. Sigue siendo una alternativa de operación; no representa el diseño actual del escritorio. Los comandos `status`, `report`, `backup`, `restore` y `protect` se describen en el manual de operaciones.

## Desarrollar y comprobar

- [Contribuciones](../CONTRIBUTING.md), [skills de desarrollo](../skills/README.md).
- [Verificación de V5.7](V5_7_REVIEW.md), [base V5.6](V5_6_REVIEW.md), [integración original de V5.5](V5_5_VERIFICATION.md), [dependencias](V5_5_DEPENDENCIES.md).
- [Investigación comparativa y límites de transferencia](V5_5_RESEARCH.md).
- [Historial de decisiones y evidencia](HISTORY.md).

La evidencia fechada describe una revisión concreta. Un test verde no acredita todas las capacidades futuras; el estado actual se obtiene del código y de los checks del commit que estés usando.
