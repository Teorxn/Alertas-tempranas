# Cómo trabajamos (GitHub Flow)

1. **`main` está protegida**: nadie hace push directo y siempre debe funcionar.
2. **Una historia = un issue = una rama**, creada desde `main` actualizada.
3. **Commits pequeños y frecuentes**, con push de la rama a GitHub.
4. **Abrir la PR temprano** (como borrador si aún no está lista) y enlazar el issue con `Closes #número`.
5. **Al menos un compañero revisa y aprueba**, y las pruebas automáticas deben pasar.
6. **Merge con "Squash and merge"** y se borra la rama.
7. **Experimentos de modelos** van en ramas `exp/`: sus resultados se documentan en la PR, aunque no se haga merge.

## Nombres de ramas

`tipo/HU-xx-descripcion-corta`, en minúsculas y sin tildes.

| Tipo | Cuándo | Ejemplo |
| --- | --- | --- |
| `feature/` | Funcionalidad nueva | `feature/HU-18-api-fastapi` |
| `fix/` | Corregir un error | `fix/HU-10-fuga-nota-corte3` |
| `data/` | Datos, limpieza o análisis exploratorio | `data/HU-08-analisis-exploratorio` |
| `exp/` | Experimento de modelos | `exp/HU-13-smote` |
| `docs/` | Documentación e informes | `docs/HU-20-informe-final` |
| `chore/` | Configuración del repositorio, dependencias | `chore/HU-05-plantillas-pr` |

## Mensajes de commit

[Conventional Commits](https://www.conventionalcommits.org/es/) en español y en presente:
`feat: agrega modelo XGBoost`, `fix: quita la nota del corte 3 de las variables`, `docs: actualiza el README`.

## Flujo en comandos

```bash
git switch main
git pull
git switch -c feature/HU-xx-descripcion
# ... cambios ...
git add .
git commit -m "feat: descripción del cambio"
git push -u origin feature/HU-xx-descripcion
gh pr create --fill
```

## Datos

El repositorio es **público**. El dataset real va en `data/raw/` y está excluido por `.gitignore`: **nunca** se sube a GitHub.

## Definición de terminado

- Cumple su criterio de aceptación.
- Su PR fue revisada y aprobada por al menos un compañero.
- Las pruebas automáticas pasan.
- Está en `main` y la rama fue borrada.
- La documentación refleja el cambio.
