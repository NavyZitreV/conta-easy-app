
INSTRUCCIONES PARA IMPORTAR CONTENIDO DE TEMAS

1. Coloca tus archivos de texto en esta carpeta (`data/source_content`).
2. Nombra los archivos siguiendo este patrón: `Topic_1.txt`, `Tema_2.md`, `Topic 11.txt`, etc. (El número es lo importante).
3. Usa el siguiente formato dentro del archivo para estructurar el contenido:

   # Título del Tema (Opcional, si quieres cambiar el título actual)
   
   Aquí va el resumen o introducción del tema. Este texto aparecerá en la parte superior.

   ## Título de la Sección 1
   Contenido de la primera sección...

   ## Título de la Sección 2
   Contenido de la segunda sección...

4. Una vez listos los archivos, ejecuta el siguiente comando en la terminal:
   `python scripts/import_content.py`

5. Esto actualizará automáticamente `data/topics_content.json`, que es la base de datos usada por la aplicación y el Tutor Virtual.
