// Original synthetic material. No user files, transcripts or provider requests.
export const sources = {
  brief: {
    name: 'brief.md', label: 'Objetivo del lanzamiento',
    text: '# Norte\n\nNorte es una aplicación de notas que funciona en local.\nEl primer lanzamiento debe explicar una sola utilidad.\nEl público inicial son personas que organizan proyectos pequeños.\nLa acción principal será apuntarse a una lista de espera.\nNo publicar fechas de disponibilidad todavía.',
  },
  scope: {
    name: 'alcance.md', label: 'Lo que existe hoy',
    text: '# Alcance de la primera entrega\n\nCrear y editar notas de texto.\nGuardar los documentos en el equipo del usuario.\nExportar una nota a Markdown.\nLa sincronización entre dispositivos no está implementada.\nNo hay colaboración en tiempo real.\nLa primera entrega se revisa manualmente antes de publicarse.',
  },
  notes: {
    name: 'notas.md', label: 'Preguntas para la propuesta',
    text: '# Notas de trabajo\n\nExplicar dónde se guardan los archivos y cómo exportarlos.\nMostrar una tarea completa, desde escribir hasta guardar.\nEvitar una lista de funciones futuras en la portada.\nComprobar si el mensaje se entiende sin conocer el producto.\nEstas notas son material sintético, no entrevistas con clientes.',
  },
} as const;
export type SourceId = keyof typeof sources;
export const defaultObjective = 'Prepara el lanzamiento de Norte. Cruza el brief con el alcance real y entrégame una propuesta que pueda revisar.';
export const decisions = [
  { title: 'Una promesa concreta', body: 'Presentar Norte como un espacio local para escribir y organizar notas.', source: 'brief' as const, line: 3 },
  { title: 'Sin funciones adelantadas', body: 'Retirar la sincronización del mensaje de lanzamiento. Todavía no existe.', source: 'scope' as const, line: 6 },
  { title: 'Un siguiente paso sencillo', body: 'Cerrar la página con una lista de espera, sin anunciar una fecha.', source: 'brief' as const, line: 6 },
];
export const resultMarkdown = `# Lanzamiento de Norte

> Entrega sintética del prototipo V5.4.1. No se ejecutó un modelo.

## Recomendación
Notas locales, guardadas en tu equipo y exportables a Markdown.
La primera página debe mostrar una tarea completa y cerrar con una lista de espera.

## Decisiones
- Mantener el trabajo local como mensaje principal. [brief.md:3]
- No anunciar sincronización: no está implementada. [alcance.md:6]
- No comprometer una fecha de disponibilidad. [brief.md:7]

## Primera entrega
1. Explicar dónde se guardan los archivos.
2. Mostrar escribir, guardar y exportar una nota.
3. Preparar el texto de la lista de espera.
4. Revisar el mensaje con una persona que no conozca Norte.

## Pendiente de validar
La comprensión del mensaje y el interés del público no se han medido.
Las notas incluidas son sintéticas, no entrevistas ni testimonios.
`;
